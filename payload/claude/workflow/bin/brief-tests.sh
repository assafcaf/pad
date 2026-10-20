#!/usr/bin/env bash
# The two per-ticket test lines /pad-run adds to a brief, from the suite map.
#
#   brief-tests.sh [--map <file>] <ticket file>
#
#   Expected to touch: <test files, comma-separated>
#   Before READY: <pad-test forms>
#
# The suite map is --map, else the `Suite map:` value under the config's `## Test regime`, else
# tests/MAP.md. A map line is `<source path>: <test file>[, <test file>...]`; a ticket's Owns
# path and a map path match when one is the other or lies below it. The ticket's key is its file
# name without `.md`. A missing map gives an empty `Expected to touch:`. Exit 64: usage.

set -uo pipefail

map=""
pos=()
while [ $# -gt 0 ]; do
  case "$1" in
    --map) map="${2:-}"; shift 2 ;;
    *) pos+=("$1"); shift ;;
  esac
done
if [ "${#pos[@]}" -ne 1 ] || [ ! -f "${pos[0]}" ]; then
  echo "usage: brief-tests.sh [--map <file>] <ticket file>" >&2
  exit 64
fi
ticket="${pos[0]}"
key="$(basename "$ticket" .md)"
bin="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "$map" ]; then
  cfg="$(git rev-parse --show-toplevel 2>/dev/null || pwd)/.claude/workflow/config.md"
  if [ -f "$cfg" ]; then
    map="$(tr -d '\r' <"$cfg" | awk '
      /^## / { inreg = ($0 == "## Test regime") }
      inreg && /Suite map:/ { s = $0; sub(/.*Suite map:[ ]*/, "", s); gsub(/`/, "", s); sub(/[ ]+$/, "", s); print s; exit }')"
  fi
  [ -n "$map" ] || map="tests/MAP.md"
fi

owns="$(bash "$bin/plan-check.sh" --list "$ticket" 2>/dev/null | awk '$1 == "OWNS" { print $2 }' | tr -d '\r')"

files=""
if [ -f "$map" ]; then
  while IFS= read -r line; do
    line="${line%$'\r'}"
    case "$line" in *:*) ;; *) continue ;; esac
    src="${line%%:*}"; tests="${line#*:}"
    src="${src#"${src%%[![:space:]]*}"}"; src="${src%/}"
    [ -n "$src" ] && [ "${src#\#}" = "$src" ] || continue
    hit=0
    while IFS= read -r o; do
      [ -n "$o" ] || continue
      o="${o%/}"
      if [ "$o" = "$src" ] || [[ $src == "$o"/* ]] || [[ $o == "$src"/* ]]; then hit=1; break; fi
    done <<<"$owns"
    [ "$hit" = 1 ] || continue
    IFS=, read -ra arr <<<"$tests"
    for t in "${arr[@]}"; do
      t="${t#"${t%%[![:space:]]*}"}"; t="${t%"${t##*[![:space:]]}"}"
      [ -n "$t" ] || continue
      case ",$files," in *",$t,"*) ;; *) files="$files${files:+,}$t" ;; esac
    done
  done <"$map"
fi

echo "Expected to touch: ${files//,/, }"
echo "Before READY: bash .claude/workflow/bin/pad-test.sh --run <run> --ticket $key --role owner --tier fast; then --acceptance $key"
