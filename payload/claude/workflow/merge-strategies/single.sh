#!/usr/bin/env bash
# Strategy single: each queued ticket is merged by its own gated merge-task.sh run (through
# merge-ticket.sh), in queue order, under the drain's merge lock.
#
# stdin: `<KEY> <TASK_HEAD> <RED>` per line. stdout: one result line per ticket.

set -uo pipefail

bin="${PAD_BIN:?PAD_BIN is not set}"

while read -r key head red _; do
  [ -n "${key:-}" ] || continue
  out="$(bash "$bin/merge-ticket.sh" --run "$PAD_RUN" "$key" "$head" "$red" 2>&1 </dev/null | tr -d '\r')"
  line="$(printf '%s\n' "$out" | grep -E '^(MERGED|REJECTED|CONFLICT|ERROR)' | tail -n 1)"
  case "$line" in
    "MERGED "*) echo "MERGED $key ${line#MERGED }" | awk '{print $1, $2, $NF}' ;;
    "") echo "ERROR $key: merge-ticket.sh printed no result: $(printf '%s' "$out" | tail -n 3 | tr '\n' ' ')" ;;
    *) printf '%s\n' "$line" ;;
  esac
done
