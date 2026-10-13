#!/usr/bin/env bash
# test-authoring check for no-fixed-sleeps. Args: <base> <head> <added-file>, whose lines are
# <path> TAB <added line>. Prints each added sleep(<literal>) of 0.5 s or more; exit 1 if any.
set -uo pipefail
out="$(awk '{
  i = index($0, "\t"); path = substr($0, 1, i - 1); s = substr($0, i + 1)
  if (match(s, /sleep\([ ]*[0-9]+(\.[0-9]*)?[ ]*\)/)) {
    v = substr(s, RSTART + 6, RLENGTH - 7); gsub(/ /, "", v)
    if (v + 0 >= 0.5) print path ": " s
  }
}' "$3")"
[ -z "$out" ] && exit 0
printf '%s\n' "$out"
exit 1
