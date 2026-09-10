#!/usr/bin/env bash
# Print the track floor a diff justifies: "execution" or "mechanical".
#
# This is the dynamic half of the process. PROJ-31 was a 40-episode collection run that shipped
# zero lines of code, and it received a worker, an independent reviewer, two review rounds, a
# task-agent verdict and a manager ruling -- 1,039 lines of blackboard prose and five findings,
# all withdrawn. A task whose diff touches no executable file has nothing for a falsifier to
# falsify, and its evidence is its deliverable.
#
# Usage: track-floor.sh <base> [<head>]
#
# "execution"  the diff touches no executable path. The task IS execution, whatever the plan
#              said, and its falsifier and reading pass are skipped.
# "mechanical" the diff touches code. The planned track stands, and may be upgraded to
#              judgment but never lowered below this without a manager's ruling.
#
# The judgment track is never inferred here: "can be silently wrong" is a property of what the
# code means, and no diff stat knows that.

set -uo pipefail

base="${1:?usage: track-floor.sh <base> [<head>]}"
head="${2:-HEAD}"

CODE_PATHS=(service scripts docker config tests gates)

changed=$(git diff --name-only "${base}..${head}" -- "${CODE_PATHS[@]}" 2>/dev/null || true)

if [ -z "$changed" ]; then
  echo "execution"
  echo "  ${base}..${head} touches no path under: ${CODE_PATHS[*]}" >&2
  echo "  This task ships no executable code. Skip the falsifier and the reading pass." >&2
else
  echo "mechanical"
  n=$(printf '%s\n' "$changed" | wc -l | tr -d ' ')
  echo "  ${base}..${head} touches ${n} executable file(s):" >&2
  printf '%s\n' "$changed" | head -10 | sed 's/^/    /' >&2
fi
