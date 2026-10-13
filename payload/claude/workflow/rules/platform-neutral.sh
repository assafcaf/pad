#!/usr/bin/env bash
# test-authoring check for platform-neutral. Args: <base> <head> <added-file>, whose lines are
# <path> TAB <added line>. Prints each added line that skips by platform; exit 1 if any.
set -uo pipefail
out="$(awk '{
  i = index($0, "\t"); path = substr($0, 1, i - 1); s = substr($0, i + 1)
  if (s ~ /(skipif|skip\()/ && s ~ /(sys\.platform|os\.name|platform\.system)/) print path ": " s
}' "$3")"
[ -z "$out" ] && exit 0
printf '%s\n' "$out"
exit 1
