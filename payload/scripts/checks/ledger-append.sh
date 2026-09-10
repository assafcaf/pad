#!/usr/bin/env bash
# Run one probe and append the result to the run's ledger.
#
# The worker never edits ledger.jsonl by hand and never re-runs a probe to get a nicer number:
# every run is a line, including the ones nobody liked. This script is what makes that cheap.
#
# Usage:
#   ledger-append.sh --run <run-id> --task <task-id> --claim <n> \
#                    --probe gates/<task-id>/<n>-<slug>.sh --phase red|green [--base <sha>]
#
# Exits with the probe's own exit code when the phase expectation holds:
#   --phase red   expects non-zero. A red run that exits 0 is an error here (exit 1) -- the probe
#                 passes without the task's change, so it is not checking the task.
#   --phase green expects 0.
#
# CLAUDE.md: every execution happens on the GPU box. Run this there.

set -uo pipefail

run="" task="" claim="" probe="" phase="" base=""
while [ $# -gt 0 ]; do
  case "$1" in
    --run)   run="$2";   shift 2 ;;
    --task)  task="$2";  shift 2 ;;
    --claim) claim="$2"; shift 2 ;;
    --probe) probe="$2"; shift 2 ;;
    --phase) phase="$2"; shift 2 ;;
    --base)  base="$2";  shift 2 ;;
    *) echo "ledger-append: unknown argument $1" >&2; exit 64 ;;
  esac
done

for v in run task claim probe phase; do
  eval "val=\$$v"
  [ -n "$val" ] || { echo "ledger-append: --$v is required" >&2; exit 64; }
done
case "$phase" in red|green) ;; *) echo "ledger-append: --phase must be red or green" >&2; exit 64 ;; esac
[ -x "$probe" ] || { echo "ledger-append: $probe is not executable" >&2; exit 64; }

root=$(git rev-parse --show-toplevel)
dir="${root}/evidence/${run}/${task}"
mkdir -p "$dir"

slug=$(basename "$probe" .sh)
log="evidence/${run}/${task}/${slug}-${phase}.log"
ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
commit=$(git rev-parse HEAD)
host=$(hostname)

echo "ledger-append: ${phase} run of ${probe} at ${commit:0:7} on ${host}"

# Capture combined output. The probe's stdout is the evidence; a probe that fails silently is
# useless to whoever reads the ticket.
"$probe" > "${root}/${log}" 2>&1
code=$?

if command -v sha256sum >/dev/null 2>&1; then
  digest=$(sha256sum "${root}/${log}" | cut -d' ' -f1)
else
  digest=$(shasum -a 256 "${root}/${log}" | cut -d' ' -f1)
fi

# CLAUDE.md: host-side Python goes through uv, never an ambient interpreter.
uv run python - "$root" "$run" "$task" "$claim" "$probe" "$phase" "$commit" "$base" \
                "$code" "$host" "$ts" "$log" "$digest" <<'PY'
import json, sys
root, run, task, claim, probe, phase, commit, base, code, host, ts, log, digest = sys.argv[1:14]
entry = {
    "ts": ts, "run": run, "task": task, "claim": claim, "probe": probe,
    "commit": commit, "base": base or None, "phase": phase, "exit": int(code),
    "host": host, "stdout_sha256": digest, "stdout_path": log,
}
path = f"{root}/evidence/{run}/ledger.jsonl"
with open(path, "a", encoding="utf-8", newline="\n") as fh:
    fh.write(json.dumps(entry, sort_keys=True) + "\n")
PY

echo "  exit ${code}, output in ${log}"

if [ "$phase" = "red" ] && [ "$code" -eq 0 ]; then
  echo "ledger-append: FAIL -- a red run exited 0." >&2
  echo "  ${probe} passes without this task's change, so it is not checking this task." >&2
  echo "  Tell your task agent which probe, in one line. Recorded either way." >&2
  exit 1
fi

exit "$code"
