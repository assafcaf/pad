#!/usr/bin/env bash
# Merge strategies: one <name>.md + <script> pair per strategy in .claude/workflow/merge-strategies/.
# PAD ships its own there; a repo adds its own beside them, and /pad-update never touches a file
# PAD did not ship.
#
#   merge-strategies.sh list                    <name> TAB <script path> TAB <options>
#   merge-strategies.sh validate [--config <p>] check every pair and the config's line;
#                                               STRATEGY FAIL <name>: <why> per problem
#   merge-strategies.sh resolve [<line>]        `<name> opt=val ...` -> the script path, then one
#                                               PAD_OPT_<NAME>=<value> line per option, declared
#                                               defaults applied. With no line, the config's
#                                               `Merge strategy:` line, default `dynamic`.
#                                               `dynamic` is printed unchanged (merge.sh maps it).
#   merge-strategies.sh rehearse <name>         delegates to merge-rehearse.sh
#
# A strategy file starts with frontmatter between two `---` lines:
#   name:         the strategy's name (not `dynamic`, which is reserved)
#   script:       a file beside the .md
#   description:  one line
#   options:      optional; comma-separated <opt>=<default>
# The body says when to use it. PAD_STRATEGIES_DIR overrides the folder; the config defaults to
# .claude/workflow/config.md in the working directory.
#
# Exit 0, or 1 when validate or resolve finds a problem. Exit 64: usage.

set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dir="${PAD_STRATEGIES_DIR:-$here/../merge-strategies}"
config=".claude/workflow/config.md"

usage() { echo "usage: merge-strategies.sh list | validate [--config <path>] | resolve [<line>] | rehearse <name>" >&2; exit 64; }

# field <file> <key>: the frontmatter value of <key>, trimmed; empty when absent.
field() {
  tr -d '\r' <"$1" | awk -v k="$2" '
    NR == 1 && $0 != "---" { exit }
    NR > 1 && $0 == "---" { exit }
    NR > 1 {
      i = index($0, ":"); if (i == 0) next
      key = substr($0, 1, i - 1); gsub(/^[ \t]+|[ \t]+$/, "", key)
      if (key != k) next
      v = substr($0, i + 1); gsub(/^[ \t]+|[ \t]+$/, "", v)
      print v; exit
    }'
}

strategy_files() { for f in "$dir"/*.md; do [ -f "$f" ] && printf '%s\n' "$f"; done; }

# sname <file>: the declared name, else the file's stem.
sname() { local n; n="$(field "$1" name)"; printf '%s' "${n:-$(basename "$1" .md)}"; }

# file_of <name>: the first strategy file declaring <name>.
file_of() {
  local f
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    [ "$(sname "$f")" = "$1" ] && { printf '%s' "$f"; return 0; }
  done <<<"$(strategy_files)"
  return 1
}

# declared <file>: the option names, one per line.
declared() { field "$1" options | tr ',' '\n' | sed 's/^[[:space:]]*//; s/=.*//; s/[[:space:]]*$//' | sed '/^$/d'; }

# default_of <file> <opt>
default_of() {
  field "$1" options | tr ',' '\n' | sed 's/^[[:space:]]*//' |
    awk -F= -v o="$2" '$1 == o { sub(/^[^=]*=/, ""); gsub(/[ \t]+$/, ""); print; exit }'
}

# config_line: the value of the config's `Merge strategy:` line; empty when absent.
config_line() {
  [ -f "$config" ] || return 0
  tr -d '\r' <"$config" | awk '
    match($0, /^[ \t]*([-*][ \t]+)?\**Merge strategy:\**[ \t]*/) {
      v = substr($0, RLENGTH + 1)
      if (match(v, /`[^`]*`/)) v = substr(v, RSTART + 1, RLENGTH - 2)
      gsub(/^[ \t]+|[ \t]+$/, "", v); print v; exit
    }'
}

# check_line <line>: prints STRATEGY FAIL lines for a `<name> opt=val ...` line; returns the count.
check_line() {
  local -a words; local name f o k bad=0 d
  read -r -a words <<<"$1"
  name="${words[0]:-}"
  [ -n "$name" ] || return 0
  [ "$name" = dynamic ] && return 0
  if ! f="$(file_of "$name")"; then
    echo "STRATEGY FAIL $name: no strategy of that name in $dir"; return 1
  fi
  d="$(declared "$f")"
  for o in "${words[@]:1}"; do
    k="${o%%=*}"
    if [[ "$o" != *=* ]] || ! grep -Fxq -- "$k" <<<"$d"; then
      echo "STRATEGY FAIL $name: option '$o' is not declared (declared: $(tr '\n' ' ' <<<"$d" | sed 's/ $//'))"
      bad=$((bad + 1))
    fi
  done
  return "$bad"
}

cmd="${1:-}"; [ $# -gt 0 ] && shift
case "$cmd" in
  list)
    [ $# -eq 0 ] || usage
    while IFS= read -r f; do
      [ -n "$f" ] || continue
      printf '%s\t%s\t%s\n' "$(sname "$f")" "$dir/$(field "$f" script)" "$(field "$f" options)"
    done <<<"$(strategy_files)"
    ;;
  validate)
    if [ "${1:-}" = --config ]; then [ $# -eq 2 ] || usage; config="$2"; shift 2; fi
    [ $# -eq 0 ] || usage
    fails=0; seen=" "
    bad() { echo "STRATEGY FAIL $1: $2"; fails=$((fails + 1)); }
    while IFS= read -r f; do
      [ -n "$f" ] || continue
      stem="$(basename "$f" .md)"; n="$(sname "$f")"
      if [ "$n" = dynamic ] || [ "$stem" = dynamic ]; then bad dynamic "reserved name"; continue; fi
      for k in name script description; do
        [ -n "$(field "$f" "$k")" ] || bad "$n" "missing $k"
      done
      s="$(field "$f" script)"
      if [ -n "$s" ] && [ ! -f "$dir/$s" ]; then bad "$n" "script $s does not exist in $dir"; fi
      if [[ "$seen" == *" $n "* ]]; then bad "$n" "duplicate name"; else seen="$seen$n "; fi
    done <<<"$(strategy_files)"
    line="$(config_line)"
    if [ -n "$line" ]; then
      out="$(check_line "$line")"; rc=$?
      if [ -n "$out" ]; then printf '%s\n' "$out"; fails=$((fails + rc)); fi
    fi
    [ "$fails" -eq 0 ] || exit 1
    ;;
  resolve)
    line="${1:-}"
    [ $# -le 1 ] || usage
    [ $# -eq 1 ] || line="$(config_line)"
    line="${line:-dynamic}"
    read -r -a words <<<"$line"
    name="${words[0]}"
    if [ "$name" = dynamic ]; then echo dynamic; exit 0; fi
    out="$(check_line "$line")" || { printf '%s\n' "$out"; exit 1; }
    [ -z "$out" ] || { printf '%s\n' "$out"; exit 1; }
    f="$(file_of "$name")"
    echo "$dir/$(field "$f" script)"
    while IFS= read -r o; do
      [ -n "$o" ] || continue
      val="$(default_of "$f" "$o")"
      for w in "${words[@]:1}"; do [ "${w%%=*}" = "$o" ] && val="${w#*=}"; done
      up="$(printf '%s' "$o" | tr 'a-z-' 'A-Z_')"
      printf 'PAD_OPT_%s=%s\n' "$up" "$val"
    done <<<"$(declared "$f")"
    ;;
  rehearse)
    [ $# -eq 1 ] || usage
    exec bash "$here/merge-rehearse.sh" "$1"
    ;;
  *) usage ;;
esac
