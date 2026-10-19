#!/usr/bin/env bash
# Land one ticket: merge-task.sh with every argument read from the config, the run and the ticket.
#
#   merge-ticket.sh [--print-args] --run <id> [--expect-tree <tree>] <KEY> <TASK_HEAD> <RED>
#
# Run from any checkout of the repo. The main checkout is the parent of the git common dir; from
# it the script reads
#   .claude/workflow/config.md              Commands (setup, gate, typecheck, lint, test paths,
#                                           derived files), Protected paths, Execution (Gate,
#                                           Test workers)
#   .work/runs/<id>/tickets/<KEY>.md        title (the goal), the ids in `## Outcomes` (`- [O1]`
#                                           or `* [O1]`), the `## Protected` flag
# and finds the epic worktree at .claude/worktrees/<id>, its checked-out branch being the epic
# branch. It then runs merge-task.sh --run <id> with those arguments and prints its output
# unchanged; the exit code is merge-task.sh's.
#
# --print-args prints the resolved merge-task.sh arguments, one per line, and runs nothing, so
# merge-candidate.sh and merge-gate.sh callers can reuse them. --expect-tree is passed through.
#
# Exit 0 MERGED, 1 REJECTED or CONFLICT, 2 a missing run, ticket or config (`ERROR <KEY>: ...`),
# 64 usage.

set -uo pipefail

usage() { echo "usage: merge-ticket.sh [--print-args] --run <id> [--expect-tree <tree>] <KEY> <TASK_HEAD> <RED>" >&2; exit 64; }

run=""; expect=""; print=""
pos=()
while [ $# -gt 0 ]; do
  case "$1" in
    --print-args) print=1; shift ;;
    --run) run="${2:-}"; shift 2 ;;
    --expect-tree) expect="${2:-}"; shift 2 ;;
    *) pos+=("$1"); shift ;;
  esac
done
[ "${#pos[@]}" -eq 3 ] && [ -n "$run" ] || usage
key="${pos[0]}"; head="${pos[1]}"; red="${pos[2]}"

bin="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
err() { echo "ERROR $key: $1" >&2; exit 2; }

common="$(git rev-parse --git-common-dir 2>/dev/null)" || err "not in a git repository"
main="$(cd "$common/.." && pwd)"
cfg="$main/.claude/workflow/config.md"
ticket="$main/.work/runs/$run/tickets/$key.md"
wt="$main/.claude/worktrees/$run"
[ -f "$cfg" ] || err "no config at $cfg"
[ -d "$main/.work/runs/$run" ] || err "unknown run $run"
[ -f "$ticket" ] || err "no ticket file $ticket"
[ -d "$wt" ] || err "no epic worktree $wt"
branch="$(git -C "$wt" branch --show-current 2>/dev/null)"
[ -n "$branch" ] || err "epic worktree $wt is on no branch"

# cell <row label>: the second cell of a Commands row, CR removed.
cell() {
  tr -d '\r' <"$cfg" | awk -v k="$1" '
    /^\| / {
      line = $0; sub(/^\| */, "", line)
      i = index(line, "|"); if (i == 0) next
      label = substr(line, 1, i - 1); gsub(/[ \t]+$/, "", label)
      if (label != k) next
      rest = substr(line, i + 1); sub(/^ */, "", rest); sub(/ *\|? *$/, "", rest)
      print rest; exit
    }'
}
# cmd <row label>: the first backtick span of that cell; empty for `none` or no row.
cmd() {
  local c; c="$(cell "$1")"
  case "$c" in none*|"") return 0 ;; esac
  printf '%s\n' "$c" | awk '{ a = index($0, "`"); if (!a) exit; r = substr($0, a + 1); b = index(r, "`"); if (!b) exit; print substr(r, 1, b - 1) }'
}
# exec_value <bold label>: the first backtick span of `- **<label>:**` in the config.
exec_value() {
  tr -d '\r' <"$cfg" | awk -v k="- **$1:**" '
    index($0, k) == 1 { r = substr($0, length(k) + 1); a = index(r, "`"); if (!a) exit
      r = substr(r, a + 1); b = index(r, "`"); if (!b) exit; print substr(r, 1, b - 1); exit }'
}

setup="$(cmd "Setup in a fresh worktree")"
named="$(cmd "Run named tests")"
full="$(cmd "Full suite")"
typecheck="$(cmd "Typecheck")"
lint="$(cmd "Lint")"
paths="$(cmd "Test paths")"
gate="${full:-$named}"
[ -n "$gate" ] || err "the config has no Full suite or Run named tests command"
[ -n "$lint" ] || err "the config has no Lint command"

args=(--worktree "$wt" --branch "$branch")
[ -z "$setup" ] || args+=(--setup "$setup")
args+=(--gate "$gate" --lint "$lint")
[ -z "$typecheck" ] || args+=(--typecheck "$typecheck")
[ -z "$paths" ] || args+=(--test-paths "$paths")

# Derived files: every backtick span of the cell, `<path>: <cmd>` -> `<path>=<cmd>`.
derived_cell="$(cell "Derived files")"
case "$derived_cell" in
  none*|"") ;;
  *)
    while IFS= read -r span; do
      [ -n "$span" ] || continue
      args+=(--derived "${span%%:*}=$(printf '%s' "${span#*:}" | sed 's/^ *//')")
    done < <(printf '%s\n' "$derived_cell" | awk '{ s = $0; while ((a = index(s, "`")) > 0) { s = substr(s, a + 1); b = index(s, "`"); if (!b) break; print substr(s, 1, b - 1); s = substr(s, b + 1) } }')
    ;;
esac

if [ "$(exec_value Gate)" = affected ] && [ -n "$named" ]; then args+=(--affected "$named"); fi
workers="$(exec_value "Test workers")"
case "$workers" in ''|*[!0-9]*) ;; *) args+=(--workers "$workers") ;; esac

# Ticket: title, outcome ids, protected flag.
fm_title="$(tr -d '\r' <"$ticket" | awk '
  NR == 1 && $0 != "---" { exit }
  NR > 1 && $0 == "---" { exit }
  NR > 1 && /^title:/ { v = substr($0, 7); gsub(/^[ \t]+|[ \t]+$/, "", v); print v; exit }')"
case "$fm_title" in
  \"*\") fm_title="${fm_title#\"}"; fm_title="${fm_title%\"}" ;;
  \'*\') fm_title="${fm_title#\'}"; fm_title="${fm_title%\'}" ;;
esac
[ -n "$fm_title" ] || err "ticket $ticket has no title"
ids="$(tr -d '\r' <"$ticket" | awk '
  /^## / { sec = ($0 == "## Outcomes"); next }
  sec && /^[-*] \[[A-Za-z0-9_.-]+\]/ { s = $0; sub(/^[-*] \[/, "", s); sub(/\].*/, "", s); printf "%s%s", (n++ ? "," : ""), s }')"
protected_flag="$(tr -d '\r' <"$ticket" | awk '
  /^## / { sec = ($0 == "## Protected"); next }
  sec && NF { print tolower($1); exit }')"

args+=(--ticket "$ticket" --run "$run")
[ -z "$ids" ] || args+=(--outcomes "$ids")
if [ "$protected_flag" = yes ]; then
  globs="$(tr -d '\r' <"$cfg" | awk '
    /^## / { sec = ($0 == "## Protected paths"); next }
    sec && /^- `/ { s = substr($0, 4); b = index(s, "`"); if (b) printf "%s%s", (n++ ? " " : ""), substr(s, 1, b - 1) }')"
  [ -z "$globs" ] || args+=(--protected "$globs")
fi
[ -z "$expect" ] || args+=(--expect-tree "$expect")
args+=("$key" "$red" "$head" "$fm_title")

if [ -n "$print" ]; then
  printf '%s\n' "${args[@]}"
  exit 0
fi
exec bash "$bin/merge-task.sh" "${args[@]}"
