#!/usr/bin/env bash
# Gate one commit of a candidate worktree with the repo's own commands.
#
#   merge-gate.sh --candidate <path> [--at <commit>] [--gate full|affected|fast|lint|<command>]
#                 [--tickets <K1[,K2...]>] [--run <id>]
#   merge-gate.sh --gate heavy|epic --head <sha> [--run <id>]
#
# Run from the epic worktree: its HEAD is the epic head, and its .claude/workflow/config.md
# supplies the commands (the first backtick span of the rows `Setup in a fresh worktree`,
# `Full suite`, `Typecheck` and `Lint`). The candidate is a detached worktree (merge-candidate.sh)
# whose HEAD, or <commit> when --at is given, is checked out and gated, with the candidate as
# every command's working directory; the candidate's own head is checked out again on exit.
#
# Order: setup (only when a dependency manifest changed between the epic head and the gated
# commit) -> gate -> typecheck -> lint. Each runs through `suite-slot.sh --priority merge`. A gate
# whose failing tests all sit in test files the batch neither changed nor imports is rerun once; a
# green rerun counts. --gate full is the configured full suite, lint the configured lint command,
# anything else is run as the command itself.
#
# --gate affected runs the config's `Run named tests` command on affected-tests.sh's selection
# between the epic head and the gated commit (`gate: affected (<files>)`), or the full suite when
# the selector answers FULL (`gate: full (<reason>)`).
#
# With a `## Test regime` (a Runner and no `Tiers: none`), --gate fast runs the fast tier and then
# every --tickets ticket's acceptance tests, each through `pad-test.sh --role gate`, then the
# typecheck and lint; the Full suite row is not run. Without a regime, or with `Tiers: none`,
# --gate fast is --gate full. --gate heavy and --gate epic run that tier at --head in a side
# worktree of their own (removed on exit), so a heavy run never holds a candidate. A ticket with no
# acceptance tests is skipped. Failures are read from the adapter's results, as pad-test.sh prints them.
#
# --run <id> keeps the run's flake record (<main checkout>/.work/runs/<id>/flakes): the tests that
# failed outside the batch are appended before the rerun, and one already recorded is
# `GATE FLAKE <test>` (exit 1) with no rerun. It is also the run pad-test.sh records under, and the
# run log that takes the signals below.
#
# A green gate whose wall passes its tier's Budget prints `GATE OVER-BUDGET <tier> <wall>/<budget>`
# (seconds) and logs it: a signal for the suite owner, not a rejection.
#
# Every step is watched (merge-lib.sh, lw_*): a process the step started that is still alive when
# it ends, whatever the adapter declares, is killed and printed as `LEAK <pid> <command>`, with
# `REJECTED <KEY>: leak <n>` when the gate has one ticket, and the gate fails.
#
# Prints the failing output's tail, then `GATE PASS` (exit 0) or `GATE FAIL` (exit 1).
# Exit 2 on usage or a missing candidate or command.

set -uo pipefail

bin="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=merge-lib.sh
. "$bin/merge-lib.sh"

usage() {
  echo "usage: merge-gate.sh --candidate <path> [--at <commit>] [--gate full|affected|fast|lint|<command>] [--tickets <K,...>] [--run <id>]" >&2
  echo "       merge-gate.sh --gate heavy|epic --head <sha> [--run <id>]" >&2
  exit 2
}

wt=""; at=""; gate_opt="full"; run=""; tickets=""; head_arg=""
while [ $# -gt 0 ]; do
  case "$1" in
    --candidate) wt="${2:-}"; shift 2 ;;
    --at) at="${2:-}"; shift 2 ;;
    --gate) gate_opt="${2:-}"; shift 2 ;;
    --run) run="${2:-}"; shift 2 ;;
    --tickets) tickets="${2:-}"; shift 2 ;;
    --head) head_arg="${2:-}"; shift 2 ;;
    *) usage ;;
  esac
done
tier_gate=0
case "$gate_opt" in heavy|epic) tier_gate=1 ;; esac
if [ "$tier_gate" -eq 1 ]; then
  [ -n "$head_arg" ] || usage
else
  [ -n "$wt" ] && [ -d "$wt" ] || usage
fi

g() { git -C "$wt" "$@"; }

cfg=".claude/workflow/config.md"
[ -f "$cfg" ] || { echo "merge-gate.sh: no $cfg in $(pwd)" >&2; exit 2; }
# cmd_of <row name>: the first backtick span of the config row.
cmd_of() {
  grep -m1 -F "| $1 |" "$cfg" | sed -n 's/^[^`]*`\([^`]*\)`.*/\1/p'
}
setup="$(cmd_of "Setup in a fresh worktree")"
full="$(cmd_of "Full suite")"
typecheck="$(cmd_of "Typecheck")"
lint="$(cmd_of "Lint")"
[ -n "$lint" ] || { echo "merge-gate.sh: no Lint command in $cfg" >&2; exit 2; }

# The test regime: tiers apply when it names a Runner and does not say `Tiers: none`.
regime_sh="$(dirname "${BASH_SOURCE[0]}")/regime.sh"
regime="$(bash "$regime_sh" section --config "$cfg")"
tiered=0
if [ -n "$(bash "$regime_sh" get Runner --config "$cfg")" ]; then
  printf '%s\n' "$regime" | grep -qiE '^[-* ]*\**Tiers:\**[[:space:]]*`?none' || tiered=1
fi
# tier_budget <tier>: the Budget cell (seconds) of the tier's row; empty when there is none.
tier_budget() {
  printf '%s\n' "$regime" | awk -F'|' -v t="$1" '
    function trim(s) { gsub(/^[ \t`]+|[ \t`]+$/, "", s); return s }
    /^\|/ { if (trim($2) == t) { print trim($5); exit } }'
}

[ "$tiered" -eq 0 ] || failed_legacy=0   # under tiers, failures come from the adapter alone
tier=""
case "$gate_opt" in
  fast) if [ "$tiered" -eq 1 ]; then tier=fast; gate_opt=tiered; else gate_opt=full; fi ;;
  heavy|epic) [ "$tiered" -eq 1 ] || { echo "merge-gate.sh: --gate $gate_opt needs a ## Test regime with tiers in $cfg" >&2; exit 2; }
              tier="$gate_opt" ;;
esac

case "$gate_opt" in
  full|tiered|heavy|epic) gate="$full" ;;
  lint) gate="$lint" ;;
  affected) gate="$full" ;;
  *) gate="$gate_opt" ;;
esac
if [ -z "$tier" ] && [ -z "$gate" ]; then echo "merge-gate.sh: no Full suite command in $cfg" >&2; exit 2; fi
if [ "$gate_opt" = affected ]; then
  named="$(cmd_of "Run named tests")"
  tpaths="$(cmd_of "Test paths")"; : "${tpaths:=tests/}"
  [ -n "$named" ] || { echo "merge-gate.sh: no Run named tests command in $cfg" >&2; exit 2; }
fi

base="$(git rev-parse HEAD)"
gate_start="$(date +%s)"
side=""
gate_pid=""
log="$(mktemp)"
# The candidate goes back to the head it came with, so the next gate of it starts from there.
cleanup() {
  kill_tree "$gate_pid"
  [ -z "$lw_pid" ] || kill -9 "$lw_pid" "$lw_pid2" 2>/dev/null
  rm -f "$log"
  if [ -n "$side" ]; then
    git worktree remove --force "$side/wt" >/dev/null 2>&1
    rm -rf "$side"
  else
    g checkout -q --detach "$orig" 2>/dev/null
  fi
}
orig=""
trap cleanup EXIT

if [ "$tier_gate" -eq 1 ]; then
  side="$(mktemp -d)" || exit 2
  git worktree add -q --detach "$side/wt" "$head_arg" >/dev/null 2>&1 || { echo "merge-gate.sh: cannot check out $head_arg" >&2; exit 2; }
  wt="$side/wt"
  head="$(g rev-parse HEAD)"
else
  orig="$(g rev-parse HEAD)"
  if [ -n "$at" ]; then
    g checkout -q --detach "$at" || { echo "merge-gate.sh: cannot check out $at" >&2; exit 2; }
  fi
  head="$(g rev-parse HEAD)"
fi

runid="${run:-merge-gate}"
main="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)"
logline() { [ -z "$run" ] || bash "$bin/run-log.sh" "$run" "$1" >/dev/null 2>&1; }

fail() {
  tail -n 40 "$log"
  echo "GATE FAIL"
  exit 1
}

# leak_fail <lines>: the step left processes alive (already killed): report them and fail.
leak_fail() {
  local n line key
  n="$(printf '%s\n' "$1" | grep -c .)"
  tail -n 40 "$log"
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    echo "LEAK $line"
    logline "LEAK $line"
  done <<EOF
$1
EOF
  key="${tickets%%,*}"
  if [ -n "$key" ] && [ "$key" = "$tickets" ]; then
    echo "REJECTED $key: leak $n"
    logline "REJECTED $key: leak $n"
  fi
  echo "GATE FAIL"
  exit 1
}

# watched <cmd...>: run <cmd> into $log as a child whose tree the exit trap can kill, watching for
# processes it leaves alive. Sets the exit code in $watched_rc and the leaks in $leaks.
leaks=""; watched_rc=0
watched() {
  "$@" >"$log" 2>&1 &
  gate_pid=$!
  lw_start "$gate_pid"
  wait "$gate_pid"; watched_rc=$?
  leaks="$(lw_stop "$main"/.work/runs/"$runid"/pad-test/*.pids*)"
  gate_pid=""
}

shell_step() { (cd "$wt" && bash "$bin/suite-slot.sh" --priority merge -- bash -c "$1"); }
pt_step() { local tk="$1"; shift; (cd "$wt" && bash "$bin/pad-test.sh" --run "$runid" --ticket "$tk" --role gate "$@"); }

# step <kind> <args...>: shell <cmd> | pt <ticket> <pad-test selection...>. Returns the step's code
# and fails the gate on a leak.
step() {
  local kind="$1"; shift
  if [ "$kind" = shell ]; then watched shell_step "$@"; else watched pt_step "$@"; fi
  [ -z "$leaks" ] || leak_fail "$leaks"
  return "$watched_rc"
}

# gate_step <kind> <args...>: step, and a failure only in test files outside the batch is rerun once.
gate_step() {
  local code
  step "$@"; code=$?
  if [ "$code" -ne 0 ] && outside_only; then
    local flakes known
    if [ -n "$run" ] && flakes="$(flake_file "$run" "$PWD")"; then
      if known="$(flake_known "$flakes")"; then
        tail -n 40 "$log"
        echo "GATE FLAKE ${known% *}"
        exit 1
      fi
      flake_record "$flakes" batch
    fi
    echo "gate failed only in test files outside this batch; rerunning it once"
    step "$@"; code=$?
  fi
  return "$code"
}

if [ -n "$setup" ] && [ "$tier_gate" -eq 0 ] && g diff --name-only "$base" "$head" | grep -Eq "$MANIFESTS"; then
  step shell "$setup" || fail
fi

if [ "$gate_opt" = affected ]; then
  pick="$(cd "$wt" && bash "$bin/affected-tests.sh" "$base" "$head" --test-paths "$tpaths" | tail -n 1)"
  case "$pick" in
    "TESTS "*) gate="${named//\{tests\}/${pick#TESTS }}"
               echo "gate: affected (${pick#TESTS })" ;;
    *) echo "gate: full (${pick#FULL })" ;;
  esac
fi

case "$gate_opt" in
  heavy|epic)
    gate_step pt "$tier" --tier "$tier" || fail ;;
  tiered)
    gate_step pt gate --tier fast || fail
    for k in $(printf '%s' "$tickets" | tr ',' ' '); do
      gate_step pt "$k" --acceptance "$k"; code=$?
      # a ticket that added no acceptance tests has nothing to run
      if [ "$code" -eq 2 ] && grep -q '^PAD-TEST did not run' "$log"; then
        echo "gate: $k has no acceptance tests"; code=0
      fi
      [ "$code" -eq 0 ] || fail
    done ;;
  *)
    gate_step shell "$gate" || fail ;;
esac
if [ "$tier_gate" -eq 0 ]; then
  if [ -n "$typecheck" ]; then step shell "$typecheck" || fail; fi
  step shell "$lint" || fail
fi

if [ -n "$tier" ]; then
  budget="$(tier_budget "$tier")"
  wall=$(( $(date +%s) - gate_start ))
  case "$budget" in ''|*[!0-9]*) ;; *)
    if [ "$wall" -gt "$budget" ]; then
      echo "GATE OVER-BUDGET $tier $wall/$budget"
      logline "GATE OVER-BUDGET $tier $wall/$budget"
    fi ;;
  esac
fi
echo "GATE PASS"
