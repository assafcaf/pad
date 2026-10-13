#!/usr/bin/env bash
# Check a task branch against every submission rule.
#
#   task-submit.sh <epic head> <RED> <TASK_HEAD> [--test-paths "<pathspecs>"]
#
# Rules, in order: not-a-commit, missing-epic-head, test-changed-after-red, red-after-code,
# test-authoring, weakened-tests. A red commit is one whose subject ends in [red]. Test paths
# default to tests/. test-authoring runs the check of every test-authoring rule
# (`rules.sh list test-authoring`) over the lines the branch adds under the test paths.
# Last line: SUBMIT OK, or SUBMIT FAIL <rule>: <detail>. Exit 0 or 1. Exit 64: usage.

set -uo pipefail

paths="tests/"
pos=()
while [ $# -gt 0 ]; do
  case "$1" in
    --test-paths) paths="${2:-}"; shift 2 ;;
    *) pos+=("$1"); shift ;;
  esac
done
if [ "${#pos[@]}" -ne 3 ]; then
  echo "usage: task-submit.sh <epic head> <RED> <TASK_HEAD> [--test-paths \"<pathspecs>\"]" >&2
  exit 64
fi
epic="${pos[0]}"; red="${pos[1]}"; head="${pos[2]}"

fail() { echo "SUBMIT FAIL $1: $2"; exit 1; }
bin="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for sha in "$epic" "$red" "$head"; do
  [ "$(git cat-file -t "$sha" 2>/dev/null)" = "commit" ] || fail not-a-commit "$sha is not a commit"
done

git merge-base --is-ancestor "$epic" "$head" ||
  fail missing-epic-head "$head does not contain the epic head $epic"

# shellcheck disable=SC2086
changed="$(git diff --name-only "$red" "$head" -- $paths)"
[ -z "$changed" ] || fail test-changed-after-red "test files changed after red: $(echo $changed)"

code="$(git log --format='%h %s' "$epic..$red^" 2>/dev/null | grep -v '\[red\]$' | head -1)"
[ -z "$code" ] || fail red-after-code "code commit before red: $code"

# Added test lines, <path> TAB <line>, for the test-authoring rules' checks.
added="$(mktemp)"
trap 'rm -f "$added"' EXIT
# shellcheck disable=SC2086
git diff -U0 "$epic" "$head" -- $paths | awk '
  /^\+\+\+ / { f = substr($0, 5); sub(/^b\//, "", f); next }
  /^\+/ { print f "\t" substr($0, 2) }' >"$added"
bad=""
while IFS=$'\t' read -r rule check _; do
  [ -n "$rule" ] || continue
  out="$(bash "$check" "$epic" "$head" "$added" 2>&1)" ||
    bad="$bad${bad:+; }$rule: $(echo "$out" | head -n 3 | tr '\n' ' ')"
done <<<"$(bash "$bin/rules.sh" list test-authoring)"
[ -z "$bad" ] || fail test-authoring "$bad"

out="$(bash "$bin/weakened-tests.sh" "$epic" "$head")" ||
  fail weakened-tests "$(echo "$out" | tr '\n' ' ')"

echo "SUBMIT OK"
