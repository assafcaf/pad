#!/usr/bin/env bash
# The only way tests run. Selects by tier, ids, the failed ones or a ticket's acceptance tests,
# applies the repeat, rerun and fix-loop limits, admits and contains the run (suite-slot.sh,
# pad-proc.sh), runs and reads the project's runner only through its adapter, and records it.
#
#   pad-test.sh --run <id> --ticket <KEY> --role owner|test-designer|gate|suite-owner|operator
#               (--tier <name> | --ids <id>... | --failed | --acceptance <KEY>) [--workers <n>]
#   pad-test.sh --self-test | --sweep | --validate
#
# Exit: 0 pass, 1 tests failed, 2 did not run, 64 usage, 65 refused (REPEAT, RUN LIMIT, NARROW,
# TIER REFUSED), 75 CAP KILLED (re-queue; not counted).
#
# Config (`## Test regime` of .claude/workflow/config.md): `Runner: <name>`, `Repeat limit:`,
# `Ticket run limit:`, and the tiers table (Tier | Adapter selector | Per-test kill | Budget |
# Declared GB | Workers). The adapter is runners/<name>.sh, found first in the repo's
# .claude/pad-plugins/runners/, then next to this script's workflow directory. Verbs only:
# run, results, capabilities, runner-names, protected-files, acceptance-pattern, mutate.
#
# An id is the adapter's own form (pytest: `<file>::<test>`); a whole file is refused by the
# adapter with exit 64 and pad-test.sh passes that through.
#
# State, per run, under <main>/.work/runs/<id>/: gates.jsonl (one line per run), flakes,
# pad-state/ (the asks, failed ids and limits of each ticket). Only the owner and test-designer
# roles are limited and tracked; gate and suite-owner runs are recorded and never counted.

set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pad-proc.sh
. "$here/pad-proc.sh"

usage() {
  cat >&2 <<'EOF'
usage: pad-test.sh --run <id> --ticket <KEY> --role owner|test-designer|gate|suite-owner|operator
                   (--tier <name> | --ids <id>... | --failed | --acceptance <KEY>) [--workers <n>]
       pad-test.sh --self-test | --sweep | --validate
EOF
  exit 64
}

run=""; ticket=""; role=""; tier=""; accept=""; workers=""; failed=0; ids=(); have_ids=0; mode=""
while [ $# -gt 0 ]; do
  case "$1" in
    --run) run="${2:-}"; shift 2 ;;
    --ticket) ticket="${2:-}"; shift 2 ;;
    --role) role="${2:-}"; shift 2 ;;
    --tier) tier="${2:-}"; shift 2 ;;
    --acceptance) accept="${2:-}"; shift 2 ;;
    --workers) workers="${2:-}"; shift 2 ;;
    --failed) failed=1; shift ;;
    --ids)
      have_ids=1; shift
      while [ $# -gt 0 ]; do
        case "$1" in --*) break ;; esac
        ids+=("$1"); shift
      done ;;
    --self-test|--sweep|--validate) mode="$1"; shift ;;
    *) usage ;;
  esac
done

top="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "pad-test.sh: not inside a git repository" >&2; exit 2; }
main="$(pp_main)" || exit 2
cfg="$top/.claude/workflow/config.md"
[ -f "$cfg" ] || cfg="$main/.claude/workflow/config.md"

# --- config ----------------------------------------------------------------------------------

# regime_section: the lines of `## Test regime`.
regime_section() {
  [ -f "$cfg" ] || return 0
  bash "$here/regime.sh" section --config "$cfg"
}

runner_name() {
  bash "$here/regime.sh" get Runner --config "$cfg"
}

# tier_row <name>: `<selector>|<kill>|<declared GB>|<workers>`; empty when the tier is unknown.
tier_row() {
  regime_section | awk -F'|' -v t="$1" '
    function trim(s) { gsub(/^[ \t`]+|[ \t`]+$/, "", s); return s }
    /^\|/ { if (trim($2) == t) { printf "%s|%s|%s|%s\n", trim($3), trim($4), trim($6), trim($7); exit } }'
}

adapter_path() {
  local name="$1" p
  for p in "$top/.claude/pad-plugins/runners/$name.sh" "$main/.claude/pad-plugins/runners/$name.sh" \
           "$here/../runners/$name.sh"; do
    [ -f "$p" ] && { echo "$p"; return 0; }
  done
  return 1
}

# --- modes that need no selection ------------------------------------------------------------

REQUIRED_VERBS="runner-names protected-files acceptance-pattern capabilities"

if [ "$mode" = --sweep ]; then
  bash "$here/pad-proc.sh" sweep
  exit $?
fi

if [ "$mode" = --self-test ] || [ "$mode" = --validate ]; then
  rc=0
  if [ "$mode" = --self-test ]; then
    bash "$here/pad-proc.sh" self-test || rc=1
  fi
  name="$(runner_name)"
  if [ -z "$name" ]; then
    echo "pad-test: no Runner: in ## Test regime of the config" >&2
    [ "$mode" = --validate ] && rc=1
  else
    if ! adapter="$(adapter_path "$name")"; then
      echo "pad-test: no adapter runners/$name.sh" >&2; exit 1
    fi
    for v in $REQUIRED_VERBS; do
      arg=""; [ "$v" = acceptance-pattern ] && arg="KEY"
      bash "$adapter" "$v" $arg >/dev/null 2>&1 || { echo "pad-test: adapter $name lacks the $v verb" >&2; rc=1; }
    done
    caps="$(bash "$adapter" capabilities 2>/dev/null | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
    echo "ADAPTER $name capabilities: ${caps:-none}"
    # Record which extras work in host.md, when there is one.
    hm="$(pp_host_md)"
    if [ "$mode" = --self-test ] && [ -n "$hm" ] && [ -f "$hm" ]; then
      extras="$(printf '%s' "$caps" | tr ' ' '\n' | grep -E '^(contract-fast|contract-heavy|leak-check|mutation)$' | paste -sd' ' -)"
      grep -v '^Adapter extras:' "$hm" > "$hm.tmp" && printf 'Adapter extras: %s\n' "${extras:-none}" >> "$hm.tmp" && mv "$hm.tmp" "$hm"
    fi
  fi
  exit "$rc"
fi

# --- usage -----------------------------------------------------------------------------------

[ -n "$run" ] && [ -n "$ticket" ] && [ -n "$role" ] || usage
case "$role" in owner|test-designer|gate|suite-owner|operator) ;; *) usage ;; esac
nsel=$(( have_ids + failed ))
[ -z "$tier" ] || nsel=$((nsel + 1))
[ -z "$accept" ] || nsel=$((nsel + 1))
[ "$nsel" -eq 1 ] || usage
if [ "$have_ids" -eq 1 ] && [ "${#ids[@]}" -eq 0 ]; then usage; fi
case "$workers" in ''|*[!0-9]*) [ -z "$workers" ] || usage ;; esac

counted=0
case "$role" in owner|test-designer) counted=1 ;; esac

runner="$(runner_name)"
if [ -z "$runner" ]; then
  echo "pad-test: did not run: no Runner: in ## Test regime of $cfg" >&2
  exit 2
fi
adapter="$(adapter_path "$runner")" || { echo "pad-test: did not run: no adapter runners/$runner.sh" >&2; exit 2; }

# The selection.
sel_tier="fast"          # the tier whose declared figures and contract apply
if [ -n "$tier" ]; then
  row="$(tier_row "$tier")"
  [ -n "$row" ] || { echo "pad-test: unknown tier '$tier' (not in the tiers table)" >&2; exit 64; }
  selkey="tier:$tier"; selname="$tier"; sel_tier="$tier"
elif [ "$have_ids" -eq 1 ]; then
  sorted="$(printf '%s\n' "${ids[@]}" | sort -u | paste -sd, -)"
  selkey="ids:$sorted"; selname="$selkey"
elif [ "$failed" -eq 1 ]; then
  selkey="failed"; selname="failed"
else
  selkey="acceptance:$accept"; selname="$selkey"
fi
row="$(tier_row "$sel_tier")"
IFS='|' read -r t_selector t_kill t_declared t_workers <<<"$row"
case "$t_declared" in ''|*[!0-9.]*) t_declared=0 ;; esac
case "$t_kill" in ''|*[!0-9]*) t_kill="" ;; esac
case "$t_workers" in ''|*[!0-9]*) t_workers=1 ;; esac
[ -n "$workers" ] || workers="$t_workers"
[ "$workers" -ge 1 ] 2>/dev/null || workers=1

# --- state helpers ---------------------------------------------------------------------------

st="$main/.work/runs/$run/pad-state"
mkdir -p "$st" "$main/.work/runs/$run" || exit 2
tk="$(printf '%s' "$ticket" | tr -c 'A-Za-z0-9._-' '_')"
gates="$main/.work/runs/$run/gates.jsonl"
tab=$'\t'

# subtract <a> <b>: the lines of a that are not lines of b.
subtract() { if [ -s "$2" ]; then grep -vxFf "$2" "$1"; else cat "$1"; fi; return 0; }

jesc() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }

# tree_hash: the commit and a hash of the working tree (tracked and untracked, .work/ ignored).
tree_hash() {
  local head idx wt
  head="$(git rev-parse HEAD 2>/dev/null)" || head="nohead"
  idx="$(mktemp)" || { echo "$head"; return; }
  cp "$(git rev-parse --git-path index)" "$idx" 2>/dev/null || : > "$idx"
  wt="$(export GIT_INDEX_FILE="$idx"; git add -A . >/dev/null 2>&1; git rm -r -q --cached --ignore-unmatch -- .work >/dev/null 2>&1; git write-tree 2>/dev/null)"
  rm -f "$idx"
  echo "${head:0:12}.${wt:0:12}"
}
tree="$(tree_hash)"

now_s() { date +%s; }
start_s="$(now_s)"

# record <outcome> <exit> <selected> <peak>
record() {
  local wall=$(( $(now_s) - start_s ))
  [ "$wall" -ge 0 ] || wall=0
  printf '{"role":"%s","ticket":"%s","selection":"%s","tree":"%s","selected":%s,"workers":%s,"wall_s":%s,"peak_gb":%s,"exit":%s,"outcome":"%s"}\n' \
    "$(jesc "$role")" "$(jesc "$ticket")" "$(jesc "$selname")" "$(jesc "$tree")" "$3" "$workers" "$wall" "${4:-0}" "$2" "$1" >> "$gates"
}

refuse() {
  echo "$1" >&2
  record refused 65 0 0
  exit 65
}

# --- tier refusal ----------------------------------------------------------------------------

if [ -n "$tier" ] && [ "$counted" -eq 1 ]; then
  case "$tier" in heavy|epic) refuse "TIER REFUSED $tier for $role" ;; esac
fi

# --- sweep leftovers, then the cap -----------------------------------------------------------

bash "$here/pad-proc.sh" sweep || true

hm="$(pp_host_md)"
if [ -z "${PAD_MEMORY_CAP:-}" ] && { [ -z "$hm" ] || [ -z "$(pp_hostval "$hm" 'Memory cap')" ]; }; then
  echo "pad-test: no host.md: memory cap is 85% of total memory ($(pp_cap 2>/dev/null) GB)" >&2
fi

# --- limits, the classifying rerun, the fix loop (owner and test-designer only) --------------

asks="$st/$tk.asks"; runs_f="$st/$tk.runs"; failed_f="$st/$tk.failed"; phase_f="$st/$tk.phase"; retry_f="$st/$tk.retry"
touch "$asks" "$runs_f" "$failed_f"
phase="$(cat "$phase_f" 2>/dev/null)"
rerun=0
failed_ids_arg=()

if [ "$counted" -eq 1 ]; then
  n_same="$(awk -F'\t' -v s="$selkey" -v t="$tree" '$1 == s && $2 == t' "$asks" | wc -l | tr -d ' ')"
  last="$(awk -F'\t' -v s="$selkey" -v t="$tree" '$1 == s && $2 == t { o = $3 } END { print o }' "$asks")"
  if [ "$n_same" -ge 1 ]; then
    case "$last" in
      fail) if [ "$n_same" -eq 1 ]; then rerun=1; else refuse "REPEAT $selname: asked $((n_same + 1)) times on this tree"; fi ;;
      flaky) refuse "REPEAT $selname: asked again on a tree that was flaky" ;;
    esac
  fi

  if [ "$rerun" -eq 0 ]; then
    if [ "$phase" = red ]; then
      ok=0
      if [ "$selkey" = failed ]; then ok=1
      elif [ "$have_ids" -eq 1 ]; then
        ok=1
        for i in "${ids[@]}"; do grep -Fxq -- "$i" "$failed_f" || ok=0; done
      fi
      [ "$(cat "$retry_f" 2>/dev/null)" = "$selkey" ] && ok=1
      [ "$ok" -eq 1 ] || refuse "NARROW: run --failed until green"
    fi
    lim="$(bash "$here/pad-test-limits.sh" show --run "$run" --ticket "$ticket")"
    lim_repeat="$(printf '%s' "$lim" | sed -n 's/.*repeat=\([0-9]*\).*/\1/p')"
    lim_runs="$(printf '%s' "$lim" | sed -n 's/.*runs=\([0-9]*\).*/\1/p')"
    n_runs="$(wc -l < "$runs_f" | tr -d ' ')"
    if [ -n "$lim_runs" ] && [ "$n_runs" -ge "$lim_runs" ]; then
      refuse "RUN LIMIT $ticket: $n_runs runs of $lim_runs on this ticket (/pad-run raises it on the operator's word)"
    fi
    seen_tree="$(awk -F'\t' -v s="$selkey" -v t="$tree" '$1 == s && $2 == t' "$runs_f" | wc -l | tr -d ' ')"
    n_trees="$(awk -F'\t' -v s="$selkey" '$1 == s { print $2 }' "$runs_f" | sort -u | wc -l | tr -d ' ')"
    if [ -n "$lim_repeat" ] && [ "$seen_tree" -eq 0 ] && [ "$n_trees" -ge "$lim_repeat" ]; then
      refuse "REPEAT $selname: $n_trees runs of $lim_repeat on changed code (/pad-run raises it on the operator's word)"
    fi
  fi
fi

if [ "$failed" -eq 1 ]; then
  if [ ! -s "$failed_f" ]; then
    echo "pad-test: --failed: no failed ids recorded for $ticket" >&2
    exit 64
  fi
  while IFS= read -r i; do [ -n "$i" ] && failed_ids_arg+=("$i"); done < "$failed_f"
fi

# --- admission, containment, the adapter -----------------------------------------------------

caps="$(bash "$adapter" capabilities 2>/dev/null | tr '\n' ' ')"
shuffle=0
if [ "$rerun" -eq 1 ]; then case " $caps " in *" shuffle "*) shuffle=1 ;; esac; fi

# estimate = max(declared GB, highest peak of the last 5 completed runs of this selection)
estimate="$t_declared"
hist="$(for g in "$main"/.work/runs/*/gates.jsonl; do [ -f "$g" ] && grep -F "\"selection\":\"$(jesc "$selname")\"" "$g"; done 2>/dev/null |
  grep -E '"outcome":"(pass|fail|flaky)"' | tail -n 5 | sed -n 's/.*"peak_gb":\([0-9.]*\).*/\1/p' | sort -g | tail -n 1)"
if [ -n "$hist" ]; then estimate="$(awk -v a="$estimate" -v b="$hist" 'BEGIN { print (b > a ? b : a) }')"; fi

stamp="$(date +%s)-$$"
name="$role-$tk-$stamp"
rd="$st/report/$name"
mkdir -p "$rd" || exit 2
peakfile="$st/$name.peak"
exitfile="$st/$name.exit"
rm -f "$exitfile" "$peakfile"

adapter_args=(run "$rd")
if [ -n "$tier" ]; then adapter_args+=(--tier-arg "$t_selector")
elif [ "$have_ids" -eq 1 ]; then adapter_args+=(--ids "${ids[@]}")
elif [ "$failed" -eq 1 ]; then adapter_args+=(--ids "${failed_ids_arg[@]}")
else
  pat="$(bash "$adapter" acceptance-pattern "$accept" 2>/dev/null | tr -d '\r' | paste -sd' ' -)"
  [ -n "$pat" ] || { echo "pad-test: did not run: the adapter has no acceptance pattern" >&2; exit 2; }
  adapter_args+=(--tier-arg "$pat")
fi
adapter_args+=(--workers "$workers")
[ -z "$t_kill" ] || adapter_args+=(--kill-per-test "$t_kill")
[ "$shuffle" -eq 0 ] || adapter_args+=(--shuffle)

slot_args=()
[ "$role" != gate ] || slot_args+=(--priority merge)

PAD_TIER="$sel_tier" bash "$here/suite-slot.sh" ${slot_args[@]+"${slot_args[@]}"} --estimate-gb "$estimate" --workers "$workers" -- \
  bash "$here/pad-proc.sh" contain --run "$run" --role "$role" --name "$name" --peak-file "$peakfile" -- \
  bash -c 'ef="$1"; shift; "$@"; echo $? > "$ef"' pad-test-wrap "$exitfile" bash "$adapter" "${adapter_args[@]}"
rc=$?

peak=0
[ -f "$peakfile" ] && peak="$(pp_peak "$peakfile")"
case "$peak" in ''|*[!0-9.]*) peak=0 ;; esac

if [ "$rc" -eq 75 ]; then
  record "cap killed" 75 0 "$peak"
  exit 75
fi

arc=""
[ -f "$exitfile" ] && arc="$(tr -d '\r\n ' < "$exitfile")"
if [ -z "$arc" ]; then
  # The adapter never finished: admission refused (probe unavailable) or the run died.
  echo "pad-test: did not run (exit $rc before the adapter ended)" >&2
  [ "$counted" -eq 0 ] || printf '%s\t%s\n' "$selkey" "$tree" >> "$runs_f"
  record "did not run" 2 0 "$peak"
  exit 2
fi
if [ "$arc" -eq 64 ]; then exit 64; fi

bash "$adapter" results "$rd" 2>/dev/null | tr -d '\r' > "$rd/results.lines"
selected="$(grep -cE '^(pass|failure|error|skipped) ' "$rd/results.lines")"
nfail="$(grep -cE '^(failure|error) ' "$rd/results.lines")"
# An id is the line's second field; the vitest form `<file> > <suite> > <test>` runs to the first
# word after its last ` > ` (a title with spaces is matched by its first word: a superset run).
id_of() {
  awk '{ sub(/^[a-z]+ /, "")
         if (index($0, " > ")) {
           rest = $0; off = 0
           while ((i = index(rest, " > ")) > 0) { off += i + 2; rest = substr(rest, i + 3) }
           j = index(rest, " "); if (j > 0) print substr($0, 1, off + j - 1); else print $0
         } else print $1 }'
}
grep -E '^(failure|error) ' "$rd/results.lines" | id_of > "$rd/new_failed"
grep -E '^pass ' "$rd/results.lines" | id_of > "$rd/passed"

if [ "$selected" -eq 0 ] && [ "$arc" -ne 0 ]; then
  outcome="did not run"; code=2
elif [ "$nfail" -gt 0 ] || [ "$arc" -ne 0 ]; then
  outcome="fail"; code=1
else
  outcome="pass"; code=0
fi

if [ "$rerun" -eq 1 ] && [ "$outcome" = pass ]; then
  outcome="flaky"; code=1
  echo "FLAKY $selname on $ticket: failed, then passed in a fresh shuffled process; not green"
  printf 'FLAKY %s %s %s %s\n' "$ticket" "$selname" "$tree" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$main/.work/runs/$run/flakes"
fi

# --- state -----------------------------------------------------------------------------------

if [ "$counted" -eq 1 ]; then
  printf '%s\t%s\t%s\n' "$selkey" "$tree" "$outcome" >> "$asks"
  [ "$rerun" -eq 1 ] || printf '%s\t%s\n' "$selkey" "$tree" >> "$runs_f"
  if [ "$outcome" != flaky ]; then
    case "$outcome" in
      fail)
        { subtract "$failed_f" "$rd/passed"; cat "$rd/new_failed"; } | grep -v '^$' | sort -u > "$failed_f.new"
        mv "$failed_f.new" "$failed_f"
        echo red > "$phase_f"; rm -f "$retry_f" ;;
      "did not run")
        printf '%s\n' "$selkey" > "$retry_f" ;;
      pass)
        if [ "$selkey" = failed ]; then : > "$failed_f"
        else
          subtract "$failed_f" "$rd/passed" | grep -v '^$' > "$failed_f.new"
          mv "$failed_f.new" "$failed_f"
        fi
        if [ "$phase" = wider ]; then : > "$phase_f"
        elif [ "$phase" = red ] && [ ! -s "$failed_f" ]; then echo wider > "$phase_f"; fi
        rm -f "$retry_f" ;;
    esac
  fi
fi

record "$outcome" "$code" "$selected" "$peak"
echo "PAD-TEST $outcome $selname selected=$selected exit=$code"
[ "$nfail" -eq 0 ] || grep -E '^(failure|error) ' "$rd/results.lines" | head -n 20
exit "$code"
