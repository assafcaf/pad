#!/usr/bin/env bash
# test-removal check for ported-from. Args: <base> <head> <removed-file>. Prints the removed
# tests that some file at <head> names in a `ported-from: <file>::<name>` marker.
set -uo pipefail
base="$1"; head="$2"; removed="$3"
marks="$(git grep -h -I -E 'ported-from:[[:space:]]*[^[:space:]]+::' "$head" 2>/dev/null | tr -d '\r' |
  sed -nE 's/.*ported-from:[[:space:]]*([^[:space:]]+::[A-Za-z0-9_]+).*/\1/p' | sort -u)"
while IFS=$'\t' read -r path name; do
  [ -n "$path" ] || continue
  printf '%s\n' "$marks" | grep -qxF "$path::$name" && printf '%s\t%s\n' "$path" "$name"
done <"$removed"
exit 0
