#!/usr/bin/env bash
# repo-lint check for scope-docs-updated: scope-docs-updated.sh <epic head> <task head>
# Exit 1 when the diff changes non-test, non-document files and no Markdown file.
set -uo pipefail
epic="${1:?epic head}"; head="${2:?task head}"
code=0; docs=0; first=""
while IFS= read -r f; do
  [ -n "$f" ] || continue
  case "$f" in
    *.md) docs=1 ;;
    tests/*|test/*|*/tests/*|*/test/*|*_test.*|*.test.*|test_*) ;;
    *) code=1; [ -n "$first" ] || first="$f" ;;
  esac
done <<<"$(git diff --name-only --no-renames "$epic" "$head")"
if [ "$code" = 1 ] && [ "$docs" = 0 ]; then
  echo "scope-docs-updated: $first changed and no Markdown file did"
  exit 1
fi
exit 0
