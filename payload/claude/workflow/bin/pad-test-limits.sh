#!/usr/bin/env bash
# A ticket's repeat and run limits, as pad-test.sh reads them.
#
#   pad-test-limits.sh show  --run <id> --ticket <KEY>
#   pad-test-limits.sh raise --run <id> --ticket <KEY> [--repeat <n>] [--runs <n>]
#
# Both print `LIMITS <KEY> repeat=<n> runs=<n>`: the config's `Repeat limit:` and `Ticket run
# limit:` (defaults 3 and 12), or what `raise` set for that ticket in that run. Only /pad-run, on
# the operator's word, calls `raise`. The override lives in
# <main>/.work/runs/<id>/pad-state/limits.<KEY>.
#
# Exit 0; 64 on usage; 2 outside a git repository.

set -uo pipefail

usage() { echo "usage: pad-test-limits.sh show|raise --run <id> --ticket <KEY> [--repeat <n>] [--runs <n>]" >&2; exit 64; }

verb="${1:-}"
[ $# -gt 0 ] && shift
case "$verb" in show|raise) ;; *) usage ;; esac

run=""; ticket=""; repeat=""; runs=""
while [ $# -gt 0 ]; do
  case "$1" in
    --run) run="${2:-}"; shift 2 ;;
    --ticket) ticket="${2:-}"; shift 2 ;;
    --repeat) repeat="${2:-}"; case "$repeat" in ''|*[!0-9]*) usage ;; esac; shift 2 ;;
    --runs) runs="${2:-}"; case "$runs" in ''|*[!0-9]*) usage ;; esac; shift 2 ;;
    *) usage ;;
  esac
done
[ -n "$run" ] && [ -n "$ticket" ] || usage
[ "$verb" = show ] || [ -n "$repeat" ] || [ -n "$runs" ] || usage

paths="$(git rev-parse --show-toplevel --git-common-dir 2>/dev/null)" || { echo "pad-test-limits.sh: not inside a git repository" >&2; exit 2; }
top="$(printf '%s\n' "$paths" | sed -n 1p)"
main="$(cd "$top" && cd "$(printf '%s\n' "$paths" | sed -n 2p)/.." && pwd)" || exit 2

cfg="$top/.claude/workflow/config.md"
[ -f "$cfg" ] || cfg="$main/.claude/workflow/config.md"
cfgnum() {
  [ -f "$cfg" ] || return 0
  sed -n "s/^[-* ]*\**$1:\**[[:space:]]*\([0-9][0-9]*\).*/\1/p" "$cfg" | head -n 1
}
def_repeat="$(cfgnum 'Repeat limit')"; [ -n "$def_repeat" ] || def_repeat=3
def_runs="$(cfgnum 'Ticket run limit')"; [ -n "$def_runs" ] || def_runs=12

dir="$main/.work/runs/$run/pad-state"
safe="$(printf '%s' "$ticket" | tr -c 'A-Za-z0-9._-' '_')"
file="$dir/limits.$safe"

cur_repeat="$def_repeat"; cur_runs="$def_runs"
if [ -f "$file" ]; then
  v="$(sed -n 's/^repeat=//p' "$file" | head -n 1 | tr -d '\r')"; [ -z "$v" ] || cur_repeat="$v"
  v="$(sed -n 's/^runs=//p' "$file" | head -n 1 | tr -d '\r')"; [ -z "$v" ] || cur_runs="$v"
fi

if [ "$verb" = raise ]; then
  [ -z "$repeat" ] || cur_repeat="$repeat"
  [ -z "$runs" ] || cur_runs="$runs"
  mkdir -p "$dir" || exit 2
  printf 'repeat=%s\nruns=%s\n' "$cur_repeat" "$cur_runs" > "$file"
fi

echo "LIMITS $ticket repeat=$((10#$cur_repeat)) runs=$((10#$cur_runs))"
