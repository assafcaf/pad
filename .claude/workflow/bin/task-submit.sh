#!/usr/bin/env bash
# Check a task branch against every submission rule.
#
#   task-submit.sh <epic head> <RED> <TASK_HEAD> [--test-paths "<pathspecs>"] [--ticket <path>]
#
# Rules, in order: not-a-commit, missing-epic-head, test-changed-after-red, red-after-code,
# test-authoring, weakened-tests, ownership. A red commit is one whose subject ends in [red].
# Test paths default to tests/. test-authoring runs the check of every test-authoring rule
# (`rules.sh list test-authoring`) over the lines the branch adds under the test paths.
# ownership runs only with --ticket: every path changed between the epic head and TASK_HEAD
# must lie in the ticket's Owns or Touches (read by `plan-check.sh --list`; a directory covers
# everything below it), or be a test-path file the red commit added or changed. A path covered
# only by Touches may gain lines but not lose any (git diff --numstat). It fails as
# `ownership: <path>` or `ownership: <path> (Touches is append-only)`.
# Last line: SUBMIT OK, or SUBMIT FAIL <rule>: <detail>. Exit 0 or 1. Exit 64: usage.

set -uo pipefail

paths="tests/"
ticket=""
pos=()
while [ $# -gt 0 ]; do
  case "$1" in
    --test-paths) paths="${2:-}"; shift 2 ;;
    --ticket) ticket="${2:-}"; [ -n "$ticket" ] || ticket="/nonexistent"; shift; [ $# -eq 0 ] || shift ;;
    *) pos+=("$1"); shift ;;
  esac
done
if [ "${#pos[@]}" -ne 3 ] || { [ -n "$ticket" ] && [ ! -f "$ticket" ]; }; then
  echo "usage: task-submit.sh <epic head> <RED> <TASK_HEAD> [--test-paths \"<pathspecs>\"] [--ticket <path>]" >&2
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

if [ -n "$ticket" ]; then
  list="$(bash "$bin/plan-check.sh" --list "$ticket")" || fail ownership "cannot read $ticket"
  owns=(); touches=()
  while read -r kind p; do
    case "$kind" in OWNS) owns+=("$p") ;; TOUCHES) touches+=("$p") ;; esac
  done <<<"$list"
  # under <file> <path>...: the file is one of the paths, or below one of them.
  under() {
    local f="$1" p; shift
    for p in "$@"; do
      if [ "$f" = "$p" ] || [[ $f == "$p"/* ]]; then return 0; fi
    done
    return 1
  }
  # shellcheck disable=SC2086
  redtests="$(git diff --name-only --no-renames "$epic" "$red" -- $paths)"
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    under "$f" ${owns[@]+"${owns[@]}"} && continue
    [ -n "$redtests" ] && grep -qxF -- "$f" <<<"$redtests" && continue
    under "$f" ${touches[@]+"${touches[@]}"} || fail ownership "$f"
    del="$(git diff --numstat --no-renames "$epic" "$head" -- "$f" | awk '{ print $2 }')"
    [ "$del" = 0 ] || fail ownership "$f (Touches is append-only)"
  done <<<"$(git diff --name-only --no-renames "$epic" "$head")"
fi

echo "SUBMIT OK"
