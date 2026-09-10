#!/usr/bin/env bash
# Every standing check, in one command. Part of the integration gate.
#
#   timeout 420 uv run pytest -q -rs && scripts/checks/run-checks.sh <base> <head>
#
# Usage: run-checks.sh <base> [<head>] [--run <run-id>] [--task <task-id>]
#
# Each of these replaces a finding that PROJ-17 discovered by hand, late, with an agent:
#
#   no-secrets     two credential exposures, both caught only because the manager broke its own
#                  prompt and re-ran git log -p itself
#   exec-bits      final review finding 6 -- three documented commands failed on a fresh clone
#   citations      final review finding 1, the run's only Critical
#   verify-ledger  final review finding 4 -- a test that could not fail for the flag it guarded
#   state-moved    raised as prose twice, adjudicated twice
#
# A check that finds something is not a review finding. It is a failed gate: nothing merges, and
# there is nothing to rebut.

set -uo pipefail

base="${1:?usage: run-checks.sh <base> [<head>] [--run <run-id>] [--task <task-id>]}"
shift
head="HEAD"
run_id=""
task_id=""

if [ $# -gt 0 ] && [ "${1#--}" = "$1" ]; then head="$1"; shift; fi
while [ $# -gt 0 ]; do
  case "$1" in
    --run)  run_id="$2"; shift 2 ;;
    --task) task_id="$2"; shift 2 ;;
    *) echo "run-checks: unknown argument $1" >&2; exit 64 ;;
  esac
done

here="$(cd "$(dirname "$0")" && pwd)"
rc=0
declare -a results=()

record() {
  local name="$1" code="$2"
  if [ "$code" -eq 0 ]; then results+=("  ok    ${name}"); else results+=("  FAIL  ${name}"); rc=1; fi
}

echo "=== standing checks: ${base}..${head} ==="
echo

echo "--- no-secrets"
"${here}/no-secrets.sh" "$base" "$head"; record no-secrets $?
echo

echo "--- exec-bits"
"${here}/exec-bits.sh"; record exec-bits $?
echo

echo "--- citations"
uv run python "${here}/citations.py"; record citations $?
echo

echo "--- state-moved"
"${here}/state-moved.sh" "$base" "$head"; record state-moved $?
echo

echo "--- verify-ledger"
if [ -n "$run_id" ]; then
  if [ -n "$task_id" ]; then
    uv run python "${here}/verify-ledger.py" "$run_id" --task "$task_id"; record verify-ledger $?
  else
    uv run python "${here}/verify-ledger.py" "$run_id"; record verify-ledger $?
  fi
else
  echo "verify-ledger: skipped -- no --run given"
  results+=("  skip  verify-ledger (no --run given)")
fi
echo

echo "=== summary ==="
printf '%s\n' "${results[@]}"
echo

if [ "$rc" -ne 0 ]; then
  echo "standing checks: RED. Nothing merges."
else
  echo "standing checks: green."
fi
exit "$rc"
