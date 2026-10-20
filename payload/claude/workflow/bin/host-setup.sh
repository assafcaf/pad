#!/usr/bin/env bash
# Write the host's facts to .claude/workflow/host.md (gitignored) and prove containment works here.
#
#   host-setup.sh [--cap <n%|nGB>]
#
# host.md, one `Key: value` per line: OS, Memory total, Memory cap (85% unless --cap, or the cap
# an earlier setup recorded), Containment (job-object or process-group), Self-test (the last line
# of the containment self-test). The self-test is PAD_SELF_TEST_CMD when set, else
# `pad-proc.sh self-test`. When it fails, setup stops: the reason goes to stderr, nothing is
# written, exit 1. `.gitignore` is made to cover host.md. PAD_MEMORY_TOTAL_GB stands in for the
# machine's total memory.
#
# Exit 0 done, 1 self-test failed, 2 not in a git repository or unreadable memory, 64 usage.

set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=pad-proc.sh
. "$here/pad-proc.sh"

cap=""
while [ $# -gt 0 ]; do
  case "$1" in
    --cap) cap="${2:-}"; shift 2 ;;
    *) echo "usage: host-setup.sh [--cap <n%|nGB>]" >&2; exit 64 ;;
  esac
done
if [ -n "$cap" ]; then
  case "$cap" in
    *%) pp_isnum "${cap%\%}" || { echo "host-setup.sh: bad --cap '$cap'" >&2; exit 64; } ;;
    *[Gg][Bb]) pp_isnum "${cap%[Gg][Bb]}" || { echo "host-setup.sh: bad --cap '$cap'" >&2; exit 64; } ;;
    *) echo "host-setup.sh: --cap takes <n%> or <n>GB" >&2; exit 64 ;;
  esac
fi

top="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "host-setup.sh: not inside a git repository" >&2; exit 2; }
file="$top/.claude/workflow/host.md"

if [ -z "$cap" ] && [ -f "$file" ]; then cap="$(pp_hostval "$file" 'Memory cap')"; fi
[ -n "$cap" ] || cap="85%"

total="$(PAD_HOST_MD=/nonexistent pp_total_gb)" || exit 2

if [ -n "${PAD_SELF_TEST_CMD:-}" ]; then
  out="$(eval "$PAD_SELF_TEST_CMD" 2>&1)"; rc=$?
else
  out="$(bash "$here/pad-proc.sh" self-test 2>&1)"; rc=$?
fi
if [ "$rc" -ne 0 ]; then
  echo "host-setup.sh: the containment self-test failed (exit $rc), setup stops:" >&2
  printf '%s\n' "$out" >&2
  exit 1
fi
result="$(printf '%s\n' "$out" | tail -n 1)"
mode="$(printf '%s\n' "$result" | awk '{ print $NF }')"
case "$mode" in job-object|process-group) ;; *) mode="$(pp_contain_mode)" ;; esac

case "$(uname -s 2>/dev/null)" in
  MINGW*|MSYS*|CYGWIN*) os=windows ;;
  Darwin) os=macos ;;
  *) os="$(uname -s | tr 'A-Z' 'a-z')" ;;
esac

mkdir -p "$(dirname "$file")" || exit 2
{
  printf 'OS: %s\n' "$os"
  printf 'Memory total: %s GB\n' "$total"
  printf 'Memory cap: %s\n' "$cap"
  printf 'Containment: %s\n' "$mode"
  printf 'Self-test: %s\n' "$result"
} > "$file"

entry=".claude/workflow/host.md"
if ! (cd "$top" && git check-ignore -q "$entry" 2>/dev/null); then
  [ -s "$top/.gitignore" ] && [ -n "$(tail -c 1 "$top/.gitignore")" ] && printf '\n' >> "$top/.gitignore"
  printf '%s\n' "$entry" >> "$top/.gitignore"
fi
echo "host-setup.sh: wrote $entry (cap $cap of $total GB, containment $mode)"
