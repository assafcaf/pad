#!/usr/bin/env bash
# STATE.md moved with the change, or a commit in the range says plainly why it did not.
#
# CLAUDE.md: "Update STATE.md in the same commit as the change it describes. Not afterwards, not
# in a follow-up. [...] If it genuinely changes none of those, say so in the commit rather than
# leaving it ambiguous." PROJ-17 raised this as a review finding twice (PROJ-28 Minor 2, PROJ-29
# Minor 5), both times as prose a human had to adjudicate.
#
# Usage: state-moved.sh <base> [<head>]

set -uo pipefail

base="${1:?usage: state-moved.sh <base> [<head>]}"
head="${2:-HEAD}"

if git diff --quiet "${base}..${head}" -- STATE.md 2>/dev/null; then
  # STATE.md did not move. Look for a commit that says so on purpose.
  if git log --format='%B' "${base}..${head}" \
     | grep -qiE 'STATE\.md|no milestone|milestone unchanged|state unchanged'; then
    echo "state-moved: ok -- STATE.md unchanged, and a commit message accounts for it"
    exit 0
  fi
  echo "state-moved: FAIL -- STATE.md did not move in ${base}..${head}, and no commit says why"
  echo "  CLAUDE.md wants one or the other. If this change shifts no milestone, closes no"
  echo "  blocker, settles no open question and changes nothing about what to do next, say"
  echo "  exactly that in the commit message."
  exit 1
fi

lines=$(git diff --numstat "${base}..${head}" -- STATE.md | awk '{print $1"+/"$2"-"}')
echo "state-moved: ok -- STATE.md moved (${lines})"
