#!/usr/bin/env bash
# Protected-surface guard for task-submit.sh: only a suite ticket may change the test regime's
# own files.
#
#   submit-surface.sh <epic head> <task head> [--ticket <path>]
#
# Prints `needs-suite-owner: <path>` for each path changed between the epic head and the task
# head that lies on the surface, and exits 1; prints nothing and exits 0 otherwise. A ticket
# whose `## Domain` is `suite` may change the surface. Run in the task's worktree.
#
# The surface: .claude/workflow/**, .claude/settings.json, CI workflow files,
# .pre-commit-config.yaml, the suite map (`Suite map:` in `## Test regime` of the config,
# default tests/MAP.md), the runner adapter's `protected-files` globs, and the globs on the
# config's `Protected surface:` line (backticked, comma-separated). A glob's `*` crosses `/`.
# Exit 64: usage.

set -uo pipefail

ticket=""
pos=()
while [ $# -gt 0 ]; do
  case "$1" in
    --ticket) ticket="${2:-}"; shift; [ $# -eq 0 ] || shift ;;
    *) pos+=("$1"); shift ;;
  esac
done
if [ "${#pos[@]}" -ne 2 ]; then
  echo "usage: submit-surface.sh <epic head> <task head> [--ticket <path>]" >&2
  exit 64
fi
epic="${pos[0]}"; head="${pos[1]}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# A suite ticket may change the surface.
if [ -n "$ticket" ] && [ -f "$ticket" ]; then
  domain="$(tr -d '\r' <"$ticket" | awk '/^## /{ on = ($0 == "## Domain"); next } on && NF { print; exit }')"
  [ "$domain" = suite ] && exit 0
fi

top="$(git rev-parse --show-toplevel 2>/dev/null)" || top="."
cfg="$top/.claude/workflow/config.md"
section=""
[ -f "$cfg" ] && section="$(bash "$here/regime.sh" section --config "$cfg")"

# line_value <key>: the text after `**Key:**` on its line.
line_value() {
  printf '%s\n' "$section" | sed -n "s/^[-* ]*\**$1:\**[[:space:]]*//p" | head -n 1
}

globs=(
  '.claude/workflow/*' '.claude/settings.json' '.github/workflows/*' '.gitlab-ci.yml'
  '.circleci/*' '.pre-commit-config.yaml'
)
map="$(line_value 'Suite map' | tr -d '`' | sed 's/[[:space:]].*//')"
globs+=("${map:-tests/MAP.md}")

while IFS= read -r g; do
  [ -n "$g" ] && globs+=("$g")
done <<<"$(line_value 'Protected surface' | grep -o '`[^`]*`' | tr -d '`')"

runner="$(bash "$here/regime.sh" get Runner --config "$cfg")"
if [ -n "$runner" ]; then
  for a in "$top/.claude/pad-plugins/runners/$runner.sh" "$here/../runners/$runner.sh"; do
    if [ -f "$a" ]; then
      while IFS= read -r g; do
        g="$(printf '%s' "$g" | tr -d '\r')"
        [ -n "$g" ] && globs+=("$g")
      done <<<"$(bash "$a" protected-files 2>/dev/null)"
      break
    fi
  done
fi

rc=0
while IFS= read -r f; do
  [ -n "$f" ] || continue
  for g in "${globs[@]}"; do
    # shellcheck disable=SC2053
    if [[ $f == $g ]]; then
      echo "needs-suite-owner: $f"
      rc=1
      break
    fi
  done
done <<<"$(git diff --name-only --no-renames "$epic" "$head")"
exit "$rc"
