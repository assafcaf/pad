#!/usr/bin/env bash
# repo-lint check for layout-as-declared: layout-as-declared.sh <epic head> <task head>
# Exit 1 when the diff adds a file that matches no glob of .claude/workflow/layout.txt.
set -uo pipefail
epic="${1:?epic head}"; head="${2:?task head}"
top="$(git rev-parse --show-toplevel 2>/dev/null)" || top="."
decl="$top/.claude/workflow/layout.txt"
[ -f "$decl" ] || exit 0
globs=()
while IFS= read -r g; do
  g="$(printf '%s' "$g" | tr -d '\r' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
  case "$g" in ''|'#'*) ;; *) globs+=("$g") ;; esac
done <"$decl"
rc=0
while IFS= read -r f; do
  [ -n "$f" ] || continue
  ok=0
  for g in ${globs[@]+"${globs[@]}"}; do
    # shellcheck disable=SC2053
    [[ $f == $g ]] && { ok=1; break; }
  done
  if [ "$ok" = 0 ]; then echo "layout-as-declared: $f is outside the declared layout"; rc=1; fi
done <<<"$(git diff --name-only --no-renames --diff-filter=A "$epic" "$head")"
exit "$rc"
