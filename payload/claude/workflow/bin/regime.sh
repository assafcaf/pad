#!/usr/bin/env bash
# regime.sh: the one reader of the config's `## Test regime` section.
#   regime.sh get <Key> [--config <path>]       the bare value of `**Key:**` (backticks, trailing
#                                                prose and CRs dropped); `Runner: none` reads as empty
#   regime.sh get-line <Key> [--config <path>]  the rest of the key's line, as written
#   regime.sh section [--config <path>]         the section's lines (the tiers table included)
# Nothing printed and exit 0 when the key, the section or the config is absent. The config is
# --config, else .claude/workflow/config.md of the current repository. When the heading appears
# twice, the last section wins.
set -u
verb="${1:-}"; [ $# -eq 0 ] || shift
key=""
if [ "$verb" = get ] || [ "$verb" = get-line ]; then key="${1:-}"; [ $# -eq 0 ] || shift; fi
cfg=""
while [ $# -gt 0 ]; do
  case "$1" in
    --config) cfg="${2:-}"; shift 2 ;;
    *) echo "usage: regime.sh get|get-line <Key> | section [--config <path>]" >&2; exit 64 ;;
  esac
done
case "$verb" in
  get|get-line) [ -n "$key" ] || { echo "regime.sh: $verb needs a key" >&2; exit 64; } ;;
  section) ;;
  *) echo "usage: regime.sh get|get-line <Key> | section [--config <path>]" >&2; exit 64 ;;
esac
if [ -z "$cfg" ]; then
  top="$(git rev-parse --show-toplevel 2>/dev/null)" || top="."
  cfg="$top/.claude/workflow/config.md"
fi
[ -f "$cfg" ] || exit 0

section="$(tr -d '\r' <"$cfg" | awk '/^## /{ on = ($0 ~ /^## Test regime/); if (on) buf = ""; next } on { buf = buf $0 "\n" } END { printf "%s", buf }')"
if [ "$verb" = section ]; then
  [ -z "$section" ] || printf '%s\n' "$section"
  exit 0
fi

line="$(printf '%s\n' "$section" | awk -v k="$key" '
  { s = $0; sub(/^[-* \t]*(\*\*)?/, "", s)
    n = length(k) + 1
    if (substr(s, 1, n) == k ":") {
      s = substr(s, n + 1); sub(/^(\*\*)?[ \t]*/, "", s); sub(/[ \t]+$/, "", s); print s; exit } }')"
if [ "$verb" = get-line ]; then
  [ -z "$line" ] || printf '%s\n' "$line"
  exit 0
fi
case "$line" in
  '`'*) val="${line#\`}"; val="${val%%\`*}" ;;
  *) val="${line%%[[:space:]]*}"; val="${val%[.,;]}" ;;
esac
if [ "$key" = Runner ] && [ "$val" = none ]; then val=""; fi
[ -z "$val" ] || printf '%s\n' "$val"
exit 0
