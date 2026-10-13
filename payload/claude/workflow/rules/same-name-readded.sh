#!/usr/bin/env bash
# test-removal check for same-name-readded. Args: <base> <head> <removed-file>. Prints the
# removed tests whose name the diff adds again anywhere. DEF_RE is weakened-tests.sh's test
# definition pattern (the name in group 2).
set -uo pipefail
base="$1"; head="$2"; removed="$3"
def_re="${DEF_RE:-[[:space:]]*(async )?def (test_[A-Za-z0-9_]+)}"
added="$(git diff -U0 "$base" "$head" | sed -nE "s/^[+]${def_re}.*/\\2/p" | sort -u)"
while IFS=$'\t' read -r path name; do
  [ -n "$path" ] || continue
  printf '%s\n' "$added" | grep -qxF "$name" && printf '%s\t%s\n' "$path" "$name"
done <"$removed"
exit 0
