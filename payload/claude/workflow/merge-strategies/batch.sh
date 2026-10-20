#!/usr/bin/env bash
# Strategy batch: gate up to `max` queued tickets once, as a candidate, then land them.
#
# stdin: `<KEY> <TASK_HEAD> <RED>` per line. stdout: one result line per ticket, plus `FLAKE <test>`.
# Green: every ticket lands through merge-ticket.sh --expect-tree <its PREFIX tree>.
# Red: bisect the prefixes for the longest green one, land it, reject the first ticket after it
# and REQUEUE the rest. A known flake (GATE FLAKE <test>) REQUEUEs the whole pass, no bisection.

set -uo pipefail

bin="${PAD_BIN:?PAD_BIN is not set}"
run="${PAD_RUN:?PAD_RUN is not set}"

keys=(); heads=(); reds=()
input="$(cat | tr -d '\r')"
while read -r key head red _; do
  [ -n "${key:-}" ] || continue
  keys+=("$key"); heads+=("$head"); reds+=("$red")
done <<EOT
$input
EOT
total="${#keys[@]}"
[ "$total" -gt 0 ] || exit 0

wt="${PAD_EPIC_WORKTREE:?PAD_EPIC_WORKTREE is not set}"
branch="${PAD_EPIC_BRANCH:?PAD_EPIC_BRANCH is not set}"
# Read-only argument resolution goes to the real merge-ticket.sh: through the engine's shim a
# --print-args call would be counted as a gate run.
real_bin="$(cd "$(dirname "${BASH_SOURCE[0]}")/../bin" && pwd)"
max="${PAD_OPT_MAX:-8}"
case "$max" in ''|*[!0-9]*|0) max=8 ;; esac

# The config comes from the epic worktree, else from the main checkout (where it may be untracked);
# merge-gate.sh runs from the directory that has it, its HEAD being the epic head.
main="$(cd "$(git -C "$wt" rev-parse --git-common-dir)/.." && pwd)"
gate_dir="$wt"
[ -f "$wt/.claude/workflow/config.md" ] || gate_dir="$main"
cfg="$gate_dir/.claude/workflow/config.md"
gate_opt=full
if [ -f "$cfg" ] && tr -d '\r' <"$cfg" | grep -Fq -- '- **Gate:** `affected`'; then gate_opt=affected; fi
# A `## Test regime` with tiers gates a candidate with the fast tier plus its tickets' acceptance tests.
if [ -f "$cfg" ]; then
  regime="$(tr -d '\r' <"$cfg" | awk '/^## /{ on = ($0 ~ /^## Test regime/); next } on')"
  if printf '%s\n' "$regime" | grep -qE '^[-* ]*\**Runner:' && ! printf '%s\n' "$regime" | grep -qiE '^[-* ]*\**Tiers:\**[[:space:]]*`?none'; then
    gate_opt=fast
  fi
fi
deps=""
if [ -f "$cfg" ]; then
  cell="$(tr -d '\r' <"$cfg" | grep -m1 -F '| Dependency directory |' | sed 's/^| *Dependency directory *| *//')"
  case "$cell" in none*|"") ;; *) deps="$(printf '%s' "$cell" | sed -n 's/^[^`]*`\([^`]*\)`.*/\1/p')" ;; esac
fi


# Candidate options, from merge-ticket.sh's resolved merge-task.sh arguments: derived files and
# test paths are the repo's; --protected is passed when any ticket of the pass is protected.
cand_args=(--worktree "$wt" --branch "$branch" --run "$run")
[ -z "$deps" ] || cand_args+=(--deps "$deps")
seen_repo="" seen_prot=""
for i in "${!keys[@]}"; do
  targs="$(cd "$wt" && bash "$real_bin/merge-ticket.sh" --print-args --run "$run" "${keys[$i]}" "${heads[$i]}" "${reds[$i]}" 2>/dev/null | tr -d '\r')"
  ta=()
  while IFS= read -r line; do ta+=("$line"); done <<EOT
$targs
EOT
  for ((j = 0; j < ${#ta[@]}; j++)); do
    case "${ta[$j]}" in
      --derived) [ -n "$seen_repo" ] || cand_args+=(--derived "${ta[$((j + 1))]}") ;;
      --test-paths) [ -n "$seen_repo" ] || cand_args+=(--test-paths "${ta[$((j + 1))]}") ;;
      --protected) [ -n "$seen_prot" ] || { cand_args+=(--protected "${ta[$((j + 1))]}"); seen_prot=1; } ;;
    esac
  done
  seen_repo=1
done

cand=""
cleanup() { [ -z "$cand" ] || bash "$bin/merge-candidate.sh" --remove "$cand" >/dev/null 2>&1; cand=""; }
trap cleanup EXIT

gate_out=""
# gate_at <commit> <count>: gate the candidate at <commit>, which carries the first <count> tickets
# of the chunk. 0 green, 1 red, 3 known flake (gate_out holds the output).
gate_at() {
  local tk
  tk="$(printf '%s,' "${pk[@]:0:$2}")"
  gate_out="$(cd "$gate_dir" && bash "$bin/merge-gate.sh" --candidate "$cand" --at "$1" --gate "$gate_opt" --tickets "${tk%,}" --run "$run" 2>&1 </dev/null | tr -d '\r')"
  case "$gate_out" in
    *"GATE FLAKE "*) return 3 ;;
    *"GATE PASS"*) return 0 ;;
    *) return 1 ;;
  esac
}

# land <index> <tree>: merge-ticket.sh --expect-tree, one result line.
land() {
  local out line k="${keys[$1]}"
  out="$(cd "$wt" && bash "$bin/merge-ticket.sh" --run "$run" --expect-tree "$2" "$k" "${heads[$1]}" "${reds[$1]}" 2>&1 </dev/null | tr -d '\r')"
  line="$(printf '%s\n' "$out" | grep -E '^(MERGED|REJECTED|CONFLICT|ERROR)' | tail -n 1)"
  case "$line" in
    "MERGED "*) echo "MERGED $k ${line#MERGED }" | awk '{print $1, $2, $NF}' ;;
    "") echo "ERROR $k: merge-ticket.sh printed no result: $(printf '%s' "$out" | tail -n 3 | tr '\n' ' ')" ;;
    *) printf '%s\n' "$line" ;;
  esac
}

requeue_from() { local j; for ((j = $1; j < total; j++)); do echo "REQUEUE ${keys[$j]}"; done; }

# index_of <key>: position in the pass.
index_of() { local i; for i in "${!keys[@]}"; do [ "${keys[$i]}" = "$1" ] && { echo "$i"; return; }; done; }

pos=0
while [ "$pos" -lt "$total" ]; do
  end=$((pos + max)); [ "$end" -le "$total" ] || end="$total"
  chunk=("${keys[@]:pos:end-pos}")
  out="$(bash "$bin/merge-candidate.sh" "${cand_args[@]}" "${chunk[@]}" 2>&1 </dev/null | tr -d '\r')"
  cand="$(printf '%s\n' "$out" | sed -n 's/^CANDIDATE //p' | head -n 1)"
  if [ -z "$cand" ]; then
    for k in "${chunk[@]}"; do echo "ERROR $k: merge-candidate.sh built no candidate: $(printf '%s' "$out" | tail -n 2 | tr '\n' ' ')"; done
    pos="$end"; continue
  fi
  printf '%s\n' "$out" | grep -E '^(CONFLICT|REJECTED|ERROR) ' || true
  pk=(); pc=(); pt=()
  prefixes="$(printf '%s\n' "$out" | grep '^PREFIX ')"
  while read -r _ k c t; do
    [ -n "$k" ] || continue
    pk+=("$k"); pc+=("$c"); pt+=("$t")
  done <<EOT
$prefixes
EOT
  n="${#pk[@]}"
  if [ "$n" -eq 0 ]; then cleanup; pos="$end"; continue; fi

  gate_at "${pc[$((n - 1))]}" "$n"; rc=$?
  lo="$n"; reason=""
  if [ "$rc" -eq 1 ]; then
    reason="$gate_out"
    lo=0; hi="$n"
    while [ $((hi - lo)) -gt 1 ]; do
      mid=$(((lo + hi) / 2))
      gate_at "${pc[$((mid - 1))]}" "$mid"; rc=$?
      if [ "$rc" -eq 0 ]; then lo="$mid"
      elif [ "$rc" -eq 1 ]; then hi="$mid"; reason="$gate_out"
      else break; fi
    done
  fi
  if [ "$rc" -eq 3 ]; then
    echo "FLAKE $(printf '%s\n' "$gate_out" | sed -n 's/^GATE FLAKE //p' | tail -n 1)"
    cleanup
    requeue_from "$pos"
    exit 0
  fi
  cleanup
  for ((i = 0; i < lo; i++)); do land "$(index_of "${pk[$i]}")" "${pt[$i]}"; done
  if [ "$lo" -lt "$n" ]; then
    echo "REJECTED ${pk[$lo]}: gate failed: $(printf '%s\n' "$reason" | tail -n 5 | tr '\n' ' ' | sed 's/  */ /g')"
    # the rest of the pass goes back to the queue, in order
    for ((i = lo + 1; i < n; i++)); do echo "REQUEUE ${pk[$i]}"; done
    requeue_from "$end"
    exit 0
  fi
  pos="$end"
done
