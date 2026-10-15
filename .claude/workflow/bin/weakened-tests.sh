#!/usr/bin/env bash
# Fail if a commit range weakens the test suite: adds a skip or xfail, adds a TODO, or removes a
# test function that no test-removal rule explains.
#
#   weakened-tests.sh [--claims <file>] <base> <head>
#
# A removed test is one whose definition the diff deletes. Each test-removal rule in
# .claude/workflow/rules/ (`rules.sh list test-removal`) runs its check over the removed tests
# and names the ones it explains: same-name-readded (moved or re-decorated), code-deleted (the
# code it tested is deleted too), ported-from (a new test carries a ported-from marker). A
# removal no rule explains fails. Nothing switches the check off.
#
# --claims <file>: the owner's REMOVALS lines, `<file>::<test> | <rule> | <reason>`. Every
# removal whose rules all have `claim: required` must be claimed, naming one of the rules that
# explains it, and every claim must name a removal. Each difference prints `MISMATCH ...`.
#
# Patterns default to pytest; override for another stack:
#   WEAK_ADDED   ERE matched against added lines   (default: skip/xfail markers, pytest.skip()
#   WEAK_TODO    ERE for an added TODO             (default: TODO; empty turns it off)
#   TEST_DEF     sed ERE capturing a test name in \2 (default: python `def test_*`)
#
# Exit 0: nothing weakened. Exit 1: offending lines printed. Exit 3: removals all explained but
# the claims don't match them. Exit 64: usage.

set -uo pipefail

claims=""
pos=()
while [ $# -gt 0 ]; do
  case "$1" in
    --claims) claims="${2:-}"; shift 2 ;;
    *) pos+=("$1"); shift ;;
  esac
done
if [ "${#pos[@]}" -ne 2 ]; then
  echo "usage: weakened-tests.sh [--claims <file>] <base> <head>" >&2
  exit 64
fi
base="${pos[0]}"
head="${pos[1]}"
added_re="${WEAK_ADDED:-(pytest\.mark\.(skip|xfail)|pytest\.skip\()}"
todo_re="${WEAK_TODO-TODO}"
def_re="${TEST_DEF:-[[:space:]]*(async )?def (test_[A-Za-z0-9_]+)}"
bin="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tab=$'\t'

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git diff -U0 "$base" "$head" >"$tmp/diff" || exit 64
rc=0

grep -E '^\+' "$tmp/diff" | grep -vE '^\+\+\+ ' >"$tmp/plus" || true
grep -E "$added_re" "$tmp/plus" >"$tmp/added" || true
if [ -s "$tmp/added" ]; then
  echo "weakened-tests: added skip/xfail:"
  sed 's/^/  /' "$tmp/added"
  rc=1
fi
if [ -n "$todo_re" ] && grep -E "$todo_re" "$tmp/plus" >"$tmp/todo"; then
  echo "weakened-tests: added TODO:"
  sed 's/^/  /' "$tmp/todo"
  rc=1
fi

# Removed test definitions, each with the file it was removed from: <path> TAB <name>.
awk '/^--- / { f = substr($0, 5); sub(/^a\//, "", f); next }
     /^\+\+\+ / { next }
     /^-/ { print f "\t" $0 }' "$tmp/diff" |
  sed -nE "s/^([^${tab}]*)${tab}-${def_re}.*/\\1${tab}\\3/p" | sort -u >"$tmp/removed"

# Run every test-removal rule's check; record <path> TAB <name> TAB <rule> TAB <claim>.
: >"$tmp/explained"
if [ -s "$tmp/removed" ]; then
  while IFS="$tab" read -r rule check claim; do
    [ -n "$rule" ] || continue
    DEF_RE="$def_re" bash "$check" "$base" "$head" "$tmp/removed" 2>/dev/null |
      tr -d '\r' | awk -v r="$rule" -v c="$claim" -F'\t' 'NF >= 2 { print $1 "\t" $2 "\t" r "\t" c }' \
      >>"$tmp/explained"
  done <<<"$(bash "$bin/rules.sh" list test-removal)"
fi

cut -f1,2 "$tmp/explained" | sort -u >"$tmp/ok"
comm -23 "$tmp/removed" "$tmp/ok" >"$tmp/gone"
if [ -s "$tmp/explained" ]; then
  echo "weakened-tests: removed tests explained by rules:"
  sort -u "$tmp/explained" | awk -F'\t' '{ print "  " $1 "::" $2 "  " $3 }'
fi
if [ -s "$tmp/gone" ]; then
  echo "weakened-tests: removed tests:"
  awk -F'\t' '{ print "  " $1 "::" $2 }' "$tmp/gone"
  rc=1
fi

if [ "$rc" -eq 0 ] && [ -n "$claims" ]; then
  # Claimed: <id> TAB <rule>. Needed: removals none of whose explaining rules is optional.
  tr -d '\r' <"$claims" | awk -F'|' 'NF >= 2 {
      id = $1; r = $2; gsub(/^[ \t]+|[ \t]+$/, "", id); gsub(/^[ \t]+|[ \t]+$/, "", r)
      if (id != "" && id != "none") print id "\t" r }' | sort -u >"$tmp/claimed"
  awk -F'\t' '{ id = $1 "::" $2; if ($4 == "optional") opt[id] = 1; all[id] = 1 }
              END { for (id in all) if (!(id in opt)) print id }' "$tmp/explained" |
    sort -u >"$tmp/needed"
  awk -F'\t' '{ print $1 "::" $2 "\t" $3 }' "$tmp/explained" | sort -u >"$tmp/allowed"
  mism=0
  while IFS= read -r id; do
    [ -n "$id" ] || continue
    grep -qF "${id}${tab}" "$tmp/claimed" ||
      { echo "MISMATCH $id: removed, explained by a rule, but not claimed in REMOVALS"; mism=1; }
  done <"$tmp/needed"
  while IFS="$tab" read -r id r; do
    [ -n "$id" ] || continue
    if ! grep -qF "${id}${tab}" "$tmp/allowed"; then
      echo "MISMATCH $id: claimed as $r, but no test of that name was removed"; mism=1
    elif ! grep -qxF "${id}${tab}${r}" "$tmp/allowed"; then
      echo "MISMATCH $id: claimed as $r, but explained by $(grep -F "${id}${tab}" "$tmp/allowed" | cut -f2 | paste -sd, -)"
      mism=1
    fi
  done <"$tmp/claimed"
  [ "$mism" -eq 0 ] || exit 3
fi

[ "$rc" -eq 0 ] && echo "weakened-tests: ok (${base:0:8}..${head:0:8})"
exit "$rc"
