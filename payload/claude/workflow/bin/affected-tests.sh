#!/usr/bin/env bash
# Select the tests a change reaches, for a merge gate run with gate=affected.
#
#   affected-tests.sh <base> <head> [--test-paths "<pathspecs>"]
#
# Changed files are `git diff --name-only <base> <head>`. The selection is every changed test
# file still present at <head>, plus every test file that imports a changed module directly or
# through other modules: a module's name is its file name without the extension, and a file
# imports it when one line has an import keyword (import, from, require, include, use) and the
# name as a word. That over-selects on common names, which costs time, never coverage.
#
# The full suite is forced when the selection can't be trusted: a conftest.py, a dependency
# manifest or lockfile, or a non-test file under the test paths (a helper or fixture) changed,
# or nothing at all was selected.
#
# Last line: `TESTS <file> ...` or `FULL <reason>`. Exit 0, or 64 on usage.

set -uo pipefail

paths="tests/"
pos=()
while [ $# -gt 0 ]; do
  case "$1" in
    --test-paths) paths="${2:-}"; shift 2 ;;
    *) pos+=("$1"); shift ;;
  esac
done
if [ "${#pos[@]}" -ne 2 ]; then
  echo "usage: affected-tests.sh <base> <head> [--test-paths \"<pathspecs>\"]" >&2
  exit 64
fi
base="${pos[0]}"; head="${pos[1]}"

manifests='^(.*/)?(conftest\.py|package\.json|package-lock\.json|npm-shrinkwrap\.json|yarn\.lock|pnpm-lock\.yaml|bun\.lockb|requirements[^/]*\.txt|pyproject\.toml|poetry\.lock|uv\.lock|Pipfile|Pipfile\.lock|setup\.py|setup\.cfg|tox\.ini|pytest\.ini|go\.mod|go\.sum|Cargo\.toml|Cargo\.lock|Gemfile|Gemfile\.lock|composer\.json|composer\.lock)$'
is_test() { [[ "$(basename "$1")" =~ ^test_.*|.*_test\.[A-Za-z]+$|.*\.(test|spec)\.[A-Za-z]+$ ]]; }
under_tests() {
  local p
  for p in $paths; do [[ "$1" == "${p%/}/"* || "$1" == "$p" ]] && return 0; done
  return 1
}

changed="$(git diff --name-only "$base" "$head")" || exit 64
selected=""
stems=""
for f in $changed; do
  if [[ "$f" =~ $manifests ]]; then echo "FULL $f changed"; exit 0; fi
  if under_tests "$f"; then
    if is_test "$f"; then
      git cat-file -e "$head:$f" 2>/dev/null && selected="$selected $f"
    else
      echo "FULL test helper $f changed"; exit 0
    fi
    continue
  fi
  s="$(basename "$f")"; s="${s%.*}"
  [ -n "$s" ] && [[ "$s" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] && stems="$stems $s"
done

kw='(^|[^[:alnum:]_])(import|from|require|include|use)([^[:alnum:]_]|$)'
# importers <pathspec...>: files at <head> under the pathspecs whose import lines name a stem.
importers() {
  local alt
  alt="$(printf '%s\n' $stems | sort -u | paste -sd'|' -)"
  [ -n "$alt" ] || return 0
  git grep -l -E -e "${kw}.*(^|[^[:alnum:]_])(${alt})([^[:alnum:]_]|$)" "$head" -- "$@" 2>/dev/null |
    sed "s#^$head:##"
}

# Close the stems over source files that import them, until nothing new is added.
if [ -n "$stems" ]; then
  excludes=()
  for p in $paths; do excludes+=(":(exclude)$p"); done
  while :; do
    added=0
    for f in $(importers . "${excludes[@]}"); do
      s="$(basename "$f")"; s="${s%.*}"
      [[ "$s" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
      [[ " $stems " == *" $s "* ]] && continue
      stems="$stems $s"; added=1
    done
    [ "$added" -eq 1 ] || break
  done
  # shellcheck disable=SC2086
  for f in $(importers $paths); do
    is_test "$f" && selected="$selected $f"
  done
fi

selected="$(printf '%s\n' $selected | awk 'NF' | sort -u | paste -sd' ' -)"
if [ -z "$selected" ]; then
  echo "FULL no test reaches the change"
  exit 0
fi
echo "TESTS $selected"
