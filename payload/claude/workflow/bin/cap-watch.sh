#!/usr/bin/env bash
# The memory watchdog: while machine memory in use is above the cap, kill one held test run per
# sample, in role order agent, then suite-owner, then gate; within a role the newest. `/pad-run`
# starts it and stops it; outside a run, admission (suite-slot.sh) still applies.
#
#   cap-watch.sh <watch run id>
#
# Samples every PAD_CAP_WATCH_INTERVAL seconds (default 2). Writes its pid to
# <main>/.work/runs/<id>/cap-watch.pid, and a killed run's line `CAP KILLED <run> at <GB>` to the
# run log (<id>/progress.md). Held runs are the ones `pad-proc.sh contain` recorded under
# .work/runs/*/pad-test/ (<name>.meta, no <name>.done). The killed run's `contain` prints the
# same line and exits 75; it is not counted toward any repeat limit (T2's record).
# Exits on its own when its starter (the parent process) is gone or its pid file is removed.
# A role outside the kill order (operator) is never killed.
#
# Exit 64 on usage, 2 outside a git repository.

set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pad-proc.sh
. "$here/pad-proc.sh"
# The starter, taken first: it can be gone before the rest of this script has run.
pp_starter
starter="$pp_starter_pid"
[ "$pp_starter_dead" -eq 0 ] || exit 0

[ $# -eq 1 ] && [ -n "$1" ] || { echo "usage: cap-watch.sh <watch run id>" >&2; exit 64; }
watch="$1"
main="$(pp_main)" || { echo "cap-watch.sh: not inside a git repository" >&2; exit 2; }
mkdir -p "$main/.work/runs/$watch" || exit 2
pidfile="$main/.work/runs/$watch/cap-watch.pid"
echo $$ > "$pidfile"
# The loop ends when its starter is gone or the pid file is removed: no PAD loop outlives the
# process that started it.

interval="${PAD_CAP_WATCH_INTERVAL:-2}"
while :; do
  [ -f "$pidfile" ] || exit 0
  [ -z "$starter" ] || pp_alive "$starter" || exit 0
  used="$(pp_mem_in_use 2>&1)"
  rc=$?
  if [ "$rc" -eq 0 ]; then
    cap="$(pp_cap 2>/dev/null)"
    if [ -n "$cap" ] && ! pp_le "$used" "$cap"; then
      base="$(pp_victim_base "$main")"
      if [ -n "$base" ]; then
        run="$(sed -n 's/^run=//p' "$base.meta" | tr -d '\r')"
        printf '%s\n' "$used" > "$base.killed"
        pp_kill_pidfile "$base.pids" >/dev/null
        bash "$here/run-log.sh" "$watch" "CAP KILLED $run at $used" >/dev/null 2>&1
      fi
    fi
  else
    echo "cap-watch.sh: $used" >&2
  fi
  sleep "$interval"
done
