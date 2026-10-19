#!/usr/bin/env bash
# Post to, or read, a run's peer channel in the main checkout, from any worktree.
#
#   channel.sh post <run id> <KEY> <line>
#   channel.sh read <run id> [--since <ts>]
#
# The channel is <main checkout>/.work/runs/<run id>/channel.md, found the way run-log.sh
# finds it (the parent of git's common dir). post appends `- <ts> <KEY>: <line>`, where <ts>
# is UTC ISO-8601 to the second (2026-10-15T10:00:00Z); the file is created with a
# `# Channel: <run id>` header when missing. The line is written literally, except that
# newlines become spaces so one post is one entry. Nothing is ever rewritten.
# read prints the entries (`- ` lines), all of them or only those whose ts is later than
# --since; a channel nobody has posted to prints nothing.
#
# Exit 0: done. Exit 1: not in a git repository, or the write failed. Exit 64: usage.

set -uo pipefail

usage() {
  echo "usage: channel.sh post <run id> <KEY> <line> | channel.sh read <run id> [--since <ts>]" >&2
  exit 64
}

[ $# -ge 2 ] || usage
cmd="$1"; run="$2"; shift 2
[ -n "$run" ] || usage
since=""
case "$cmd" in
  post) [ $# -eq 2 ] && [ -n "$1" ] || usage; key="$1"; line="$2" ;;
  read)
    if [ $# -gt 0 ]; then
      [ $# -eq 2 ] && [ "$1" = "--since" ] && [ -n "$2" ] || usage
      since="$2"
    fi ;;
  *) usage ;;
esac

# --path-format=absolute would say this directly, but it needs git 2.31.
top="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "channel: not a git repository" >&2; exit 1; }
main="$(cd "$top" && cd "$(git rev-parse --git-common-dir)/.." && pwd)" || {
  echo "channel: cannot find the main checkout" >&2; exit 1; }
dir="$main/.work/runs/$run"
file="$dir/channel.md"

if [ "$cmd" = read ]; then
  [ -f "$file" ] || exit 0
  # Entries are `- <ts> ...`; ISO-8601 UTC timestamps of one width compare as strings.
  awk -v since="$since" '/^- / { if (since == "" || $2 > since) print }' "$file"
  exit 0
fi

mkdir -p "$dir" || { echo "channel: cannot create $dir" >&2; exit 1; }
if [ ! -f "$file" ]; then
  printf '# Channel: %s\n\n' "$run" >"$file" || {
    echo "channel: cannot create $file" >&2; exit 1; }
fi
line="${line//$'\r'/ }"
line="${line//$'\n'/ }"
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
# printf, not echo: a line may start with -e or hold backslashes, and must land as given.
printf -- '- %s %s: %s\n' "$ts" "$key" "$line" >>"$file" || {
  echo "channel: cannot append to $file" >&2; exit 1; }
