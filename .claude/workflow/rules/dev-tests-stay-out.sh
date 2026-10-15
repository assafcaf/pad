#!/usr/bin/env bash
# test-authoring check for dev-tests-stay-out. Args: <base> <head> <added-file>, whose lines are
# <path> TAB <added line>. Prints each added file under the dev path and each added
# `pytest.mark.dev`; exit 1 if any. The dev path is the config's Commands `Dev tests` row
# (its first backtick span), else tests/_dev/.
set -uo pipefail
base="$1"; head="$2"
dev=""
config=".claude/workflow/config.md"
[ -f "$config" ] &&
  dev="$(tr -d '\r' <"$config" | sed -nE 's/^\|[[:space:]]*Dev tests[[:space:]]*\|[^`]*`([^`]+)`.*/\1/p' | head -n 1)"
dev="${dev:-tests/_dev/}"
dev="${dev%/}/"
out="$(git diff --name-only --diff-filter=A "$base" "$head" | grep -F "$dev" | awk -v d="$dev" 'index($0, d) == 1 { print $0 ": a dev test, committed" }')"
marks="$(awk '{ i = index($0, "\t"); s = substr($0, i + 1)
  if (s ~ /pytest\.mark\.dev([^A-Za-z0-9_]|$)/) print substr($0, 1, i - 1) ": " s }' "$3")"
out="$(printf '%s\n%s\n' "$out" "$marks" | awk 'NF')"
[ -z "$out" ] && exit 0
printf '%s\n' "$out"
exit 1
