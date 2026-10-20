#!/usr/bin/env bash
# test-removal check for drained-by-suite-owner. Args: <base> <head> <removed-file>, the removed
# file holding `<path> TAB <name>` lines. Prints the removed tests it explains: a commit in
# <base>..<head> whose subject is `suite(<KEY>): ...` carries a line
# `VERDICT <KEY> <id> promote|rewrite|retire <tier> — <why>` whose <id> is the test
# (`<path>::<name>`, or ending ` > <name>` for a runner whose ids read that way).
set -uo pipefail
base="$1"; head="$2"; removed="$3"

# Verdict lines of suite commits only.
verdicts="$(
  for c in $(git rev-list "$base..$head" 2>/dev/null); do
    case "$(git log -1 --format=%s "$c" | tr -d '\r')" in
      suite\(*\):*) git log -1 --format=%B "$c" | tr -d '\r' | grep -E '^VERDICT [^ ]+ .+ (promote|rewrite|retire) ' ;;
    esac
  done
)"
[ -n "$verdicts" ] || exit 0

esc() { printf '%s' "$1" | sed 's/[][\.*^$/+?(){}|]/\\&/g'; }
while IFS=$'\t' read -r path name; do
  [ -n "$path" ] || continue
  name="${name%$'\r'}"
  p="$(esc "$path")"; n="$(esc "$name")"
  if printf '%s\n' "$verdicts" | grep -qE "^VERDICT [^ ]+ (${p}::${n}|.* > ${n}) (promote|rewrite|retire) "; then
    printf '%s\t%s\n' "$path" "$name"
  fi
done <"$removed"
exit 0
