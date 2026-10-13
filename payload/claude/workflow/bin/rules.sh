#!/usr/bin/env bash
# Rules: one Markdown file per rule in .claude/workflow/rules/. PAD ships its own there; a repo
# adds its own beside them, and /pad-update never touches a file PAD did not ship.
#
#   rules.sh for <agent>     print the guidance of every rule whose applies-to names <agent>
#   rules.sh list <kind>     one line per rule of <kind> that has a check:
#                            <name> TAB <absolute check path> TAB <claim>
#   rules.sh validate        check every rule file; RULES FAIL <rule>: <why> per problem
#
# A rule file starts with frontmatter between two `---` lines:
#   name:        the file's name without .md
#   kind:        test-removal | test-authoring | practice
#   applies-to:  comma-separated agents (`orchestrator` is /batch-implement itself)
#   check:       optional; a script in the rules folder. Required for test-removal, not
#                allowed for practice
#   claim:       optional, test-removal only: required (default) or optional. An optional
#                rule's removals need no REMOVALS line in the owner's READY block
# The body is the guidance the named agents follow.
#
# Each kind is enforced at one point: test-removal by weakened-tests.sh, test-authoring by
# task-submit.sh, practice by the agents reading it. PAD_RULES_DIR overrides the folder.
#
# Exit 0, or 1 when validate finds a problem. Exit 64: usage.

set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dir="${PAD_RULES_DIR:-$here/../rules}"
agents_dir="${PAD_AGENTS_DIR:-$here/../../agents}"
kinds="test-removal test-authoring practice"

usage() { echo "usage: rules.sh for <agent> | list <kind> | validate" >&2; exit 64; }

# field <file> <key>: the frontmatter value of <key>, trimmed; empty when absent.
field() {
  tr -d '\r' <"$1" | awk -v k="$2" '
    NR == 1 && $0 != "---" { exit }
    NR > 1 && $0 == "---" { exit }
    NR > 1 {
      i = index($0, ":"); if (i == 0) next
      key = substr($0, 1, i - 1); gsub(/^[ \t]+|[ \t]+$/, "", key)
      if (key != k) next
      v = substr($0, i + 1); gsub(/^[ \t]+|[ \t]+$/, "", v); gsub(/^\[|\]$/, "", v)
      print v; exit
    }'
}

# body <file>: everything after the frontmatter.
body() { tr -d '\r' <"$1" | awk 'NR == 1 && $0 == "---" { fm = 1; next } fm && $0 == "---" { fm = 0; next } !fm'; }

# applies <file> <agent>: true when the rule's applies-to names <agent>.
applies() {
  local a
  for a in $(field "$1" applies-to | tr ',' ' '); do
    [ "$a" = "$2" ] && return 0
  done
  return 1
}

rule_files() { for f in "$dir"/*.md; do [ -f "$f" ] && printf '%s\n' "$f"; done; }

case "${1:-}" in
  for)
    [ $# -eq 2 ] || usage
    n=0
    while IFS= read -r f; do
      [ -n "$f" ] || continue
      applies "$f" "$2" || continue
      printf '### Rule: %s (%s)\n' "$(field "$f" name)" "$(field "$f" kind)"
      body "$f" | sed '/./,$!d'
      echo
      n=$((n + 1))
    done <<<"$(rule_files)"
    [ "$n" -gt 0 ] || echo "no rules apply to $2"
    ;;
  list)
    [ $# -eq 2 ] || usage
    while IFS= read -r f; do
      [ -n "$f" ] || continue
      [ "$(field "$f" kind)" = "$2" ] || continue
      c="$(field "$f" check)"
      [ -n "$c" ] || continue
      claim="$(field "$f" claim)"
      printf '%s\t%s\t%s\n' "$(field "$f" name)" "$(cd "$dir" && pwd)/$c" "${claim:-required}"
    done <<<"$(rule_files)"
    ;;
  validate)
    [ $# -eq 1 ] || usage
    known="orchestrator"
    for a in "$agents_dir"/*.md; do
      [ -f "$a" ] || continue
      name="$(basename "$a" .md)"
      grep -q "rules.sh for $name" "$a" && known="$known $name"
    done
    fails=0; count=0
    bad() { echo "RULES FAIL $1: $2"; fails=$((fails + 1)); }
    while IFS= read -r f; do
      [ -n "$f" ] || continue
      count=$((count + 1))
      id="$(basename "$f" .md)"
      for k in name kind applies-to; do
        [ -n "$(field "$f" "$k")" ] || bad "$id" "missing $k"
      done
      nm="$(field "$f" name)"
      [ -z "$nm" ] || [ "$nm" = "$id" ] || bad "$id" "name $nm differs from the file name"
      kind="$(field "$f" kind)"
      if [ -n "$kind" ] && [[ " $kinds " != *" $kind "* ]]; then
        bad "$id" "kind $kind has no enforcement point (one of: $kinds)"
      fi
      for a in $(field "$f" applies-to | tr ',' ' '); do
        [[ " $known " == *" $a "* ]] ||
          bad "$id" "applies-to names $a, which is no agent that loads rules (known: $known)"
      done
      c="$(field "$f" check)"
      if [ -n "$c" ]; then
        [ "$kind" = practice ] && bad "$id" "practice rules carry no check"
        [ -f "$dir/$c" ] || bad "$id" "check $c does not exist in $dir"
      elif [ "$kind" = test-removal ]; then
        bad "$id" "test-removal needs a check"
      fi
      claim="$(field "$f" claim)"
      case "$claim" in ''|required|optional) ;; *) bad "$id" "claim must be required or optional" ;; esac
    done <<<"$(rule_files)"
    if [ "$fails" -gt 0 ]; then echo "RULES FAILED $fails"; exit 1; fi
    echo "RULES OK ($count rules)"
    ;;
  *) usage ;;
esac
