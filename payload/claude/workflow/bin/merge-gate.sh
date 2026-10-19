#!/usr/bin/env bash
# Gate one commit of a candidate worktree with the repo's own commands.
#
#   merge-gate.sh --candidate <path> [--at <commit>] [--gate full|lint|<command>]
#
# Run from the epic worktree: its HEAD is the epic head, and its .claude/workflow/config.md
# supplies the commands (the first backtick span of the rows `Setup in a fresh worktree`,
# `Full suite`, `Typecheck` and `Lint`). The candidate is a detached worktree (merge-candidate.sh)
# whose HEAD, or <commit> when --at is given, is checked out and gated, with the candidate as
# every command's working directory; the candidate's own head is checked out again on exit.
#
# Order: setup (only when a dependency manifest changed between the epic head and the gated
# commit) -> gate -> typecheck -> lint. Each runs through `suite-slot.sh --priority merge`. A gate
# whose failures (pytest-style `FAILED <file>::<test>` lines) all sit in test files the batch
# neither changed nor imports is rerun once; a green rerun counts. --gate full is the configured
# full suite, lint the configured lint command, anything else is run as the command itself.
#
# --run <id> keeps the run's flake record (<main checkout>/.work/runs/<id>/flakes): the tests that
# failed outside the batch are appended before the rerun, and one already recorded is
# `GATE FLAKE <test>` (exit 1) with no rerun.
#
# Prints the failing output's tail, then `GATE PASS` (exit 0) or `GATE FAIL` (exit 1).
# Exit 2 on usage or a missing candidate or command.

set -uo pipefail

bin="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=merge-lib.sh
. "$bin/merge-lib.sh"

usage() { echo "usage: merge-gate.sh --candidate <path> [--at <commit>] [--gate full|lint|<command>] [--run <id>]" >&2; exit 2; }

wt=""; at=""; gate_opt="full"; run=""
while [ $# -gt 0 ]; do
  case "$1" in
    --candidate) wt="${2:-}"; shift 2 ;;
    --at) at="${2:-}"; shift 2 ;;
    --gate) gate_opt="${2:-}"; shift 2 ;;
    --run) run="${2:-}"; shift 2 ;;
    *) usage ;;
  esac
done
[ -n "$wt" ] && [ -d "$wt" ] || usage

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

case "$gate_opt" in
  full) gate="$full" ;;
  lint) gate="$lint" ;;
  *) gate="$gate_opt" ;;
esac
[ -n "$gate" ] || { echo "merge-gate.sh: no Full suite command in $cfg" >&2; exit 2; }

base="$(git rev-parse HEAD)"
orig="$(g rev-parse HEAD)"
if [ -n "$at" ]; then
  g checkout -q --detach "$at" || { echo "merge-gate.sh: cannot check out $at" >&2; exit 2; }
fi
head="$(g rev-parse HEAD)"

log="$(mktemp)"
gate_pid=""
# The candidate goes back to the head it came with, so the next gate of it starts from there.
trap 'kill_tree "$gate_pid"; rm -f "$log"; g checkout -q --detach "$orig" 2>/dev/null' EXIT

# run_cmd <cmd>: in the candidate, holding a merge-priority suite slot, as a child whose tree the
# exit trap can kill.
run_cmd() {
  local rc
  (cd "$wt" && bash "$bin/suite-slot.sh" --priority merge -- bash -c "$1") >"$log" 2>&1 &
  gate_pid=$!
  wait "$gate_pid"; rc=$?
  gate_pid=""
  return "$rc"
}

fail() {
  tail -n 40 "$log"
  echo "GATE FAIL"
  exit 1
}

if [ -n "$setup" ] && g diff --name-only "$base" "$head" | grep -Eq "$MANIFESTS"; then
  run_cmd "$setup" || fail
fi

run_cmd "$gate"; code=$?
if [ "$code" -ne 0 ] && outside_only; then
  if [ -n "$run" ] && flakes="$(flake_file "$run" "$PWD")"; then
    if known="$(flake_known "$flakes")"; then
      tail -n 40 "$log"
      echo "GATE FLAKE ${known% *}"
      exit 1
    fi
    flake_record "$flakes" batch
  fi
  echo "gate failed only in test files outside this batch; rerunning it once"
  run_cmd "$gate"; code=$?
fi
[ "$code" -eq 0 ] || fail
if [ -n "$typecheck" ]; then run_cmd "$typecheck" || fail; fi
run_cmd "$lint" || fail
echo "GATE PASS"
