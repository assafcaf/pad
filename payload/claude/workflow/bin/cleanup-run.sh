#!/usr/bin/env bash
# After an epic's PR has merged, remove everything its run left behind, from any worktree.
#
#   cleanup-run.sh --run <id> --epic-branch <b> [--dry-run]
#
# Refused unless the epic is merged: after `git fetch origin`, the epic tip (local branch, else
# origin/<b>) is an ancestor of origin/<default> (origin's HEAD branch, else `main`), or - since
# a squash merge breaks ancestry - `gh pr view <b> --json state -q .state` prints MERGED (gh is
# optional). Nothing is touched before that check passes.
#
# Then, all git commands run from the main checkout:
#   1. Every linked worktree on the epic branch, on a branch named in the Branch column of
#      <main>/.work/runs/<id>/board.md, or at <main>/.claude/worktrees/<id>, is removed with
#      `git worktree remove` (never --force). One with uncommitted changes or untracked files
#      that are not ignored is left, with its branch: `SKIP <path>: dirty`.
#   2. Those branches are deleted locally with `git branch -D` (allowed only because the merged
#      check passed), unless kept by step 1 or checked out in a worktree that remains. The
#      default branch is never deleted.
#   3. The epic's branch on origin is deleted (`git push origin --delete`); absent, skipped quietly.
#   4. Stale lock and pid files under the git common dir - pad-locks/merge, pad-locks/slots/*,
#      pad-locks/merge-waiting/* and pad-preview/*.pid (with its .log) - whose recorded pid is no
#      longer running. A live one is kept and not reported.
#   5. `git worktree prune`.
#   6. <main>/.work/runs/<id>/, only when nothing was skipped (a rerun needs its board.md).
#      .work/tickets/ is the local ledger and is never touched.
# Run it from the main checkout: on Windows a shell sitting in a worktree keeps it from removal.
#
# One line per action: `REMOVED worktree <path>`, `DELETED branch <b>`, `DELETED remote <b>`,
# `REMOVED lock <path>`, `REMOVED pid <path>`, `REMOVED run <dir>`, `SKIP <what>: <why>`. With
# --dry-run nothing changes and those lines are prefixed `WOULD `.
#
# Last line: `CLEANUP OK <n> removed` (exit 0; `(dry run)` appended with --dry-run) |
# `CLEANUP REFUSED <why>` (exit 1) | `CLEANUP PARTIAL <n> skipped` (exit 1). Exit 64: usage.

set -uo pipefail

usage() { echo "usage: cleanup-run.sh --run <id> --epic-branch <b> [--dry-run]" >&2; exit 64; }

run="" epic="" dry=0
while [ $# -gt 0 ]; do
  case "$1" in
    --run) [ $# -ge 2 ] || usage; run="$2"; shift 2 ;;
    --epic-branch) [ $# -ge 2 ] || usage; epic="$2"; shift 2 ;;
    --dry-run) dry=1; shift ;;
    *) usage ;;
  esac
done
[ -n "$run" ] && [ -n "$epic" ] || usage
# The run id names a directory that is removed: one plain path segment only.
case "$run" in */*|*\\*|.|..) usage ;; esac

refuse() { echo "CLEANUP REFUSED $1"; exit 1; }

top="$(git rev-parse --show-toplevel 2>/dev/null)" || refuse "not a git repository"
main="$(cd "$top" && cd "$(git rev-parse --git-common-dir)/.." && pwd)" || refuse "cannot find the main checkout"
cd "$main" || refuse "cannot enter $main"
common="$(cd "$(git rev-parse --git-common-dir)" && pwd)" || refuse "cannot find the git common dir"

# --- merged check ------------------------------------------------------------------------------
has_origin=0
git remote | grep -qx origin && has_origin=1
default=""
if [ "$has_origin" -eq 1 ]; then
  git fetch -q origin 2>/dev/null || echo "cleanup-run: git fetch origin failed; using the last fetched state" >&2
  default="$(git symbolic-ref -q refs/remotes/origin/HEAD 2>/dev/null)"
  default="${default#refs/remotes/origin/}"
  [ -n "$default" ] || default="$(git ls-remote --symref origin HEAD 2>/dev/null |
    sed -n 's|^ref: refs/heads/\([^[:space:]]*\)[[:space:]]*HEAD$|\1|p' | head -n 1)"
fi
[ -n "$default" ] || default=main
[ "$epic" != "$default" ] || refuse "$epic is the default branch"

tip="$(git rev-parse -q --verify "refs/heads/$epic^{commit}" 2>/dev/null)" ||
  tip="$(git rev-parse -q --verify "refs/remotes/origin/$epic^{commit}" 2>/dev/null)" || tip=""

merged=0
if [ -n "$tip" ] && git rev-parse -q --verify "refs/remotes/origin/$default" >/dev/null 2>&1 &&
   git merge-base --is-ancestor "$tip" "refs/remotes/origin/$default" 2>/dev/null; then
  merged=1
elif command -v gh >/dev/null 2>&1; then
  state="$(gh pr view "$epic" --json state -q .state 2>/dev/null | tr -d '\r' | tail -n 1)"
  [ "$state" = MERGED ] && merged=1
fi
[ "$merged" -eq 1 ] ||
  refuse "$epic is not merged into origin/$default and gh does not report its PR as MERGED"

# --- what belongs to the run -------------------------------------------------------------------
removed=0 skipped=0
say() {  # say <line>: an action done (or, with --dry-run, one that would be)
  if [ "$dry" -eq 1 ]; then echo "WOULD $1"; else echo "$1"; fi
  case "$1" in SKIP*) skipped=$((skipped + 1)) ;; *) removed=$((removed + 1)) ;; esac
}
norm() { (cd "$1" 2>/dev/null && pwd -P) || printf '%s' "$1"; }

rundir="$main/.work/runs/$run"
board_branches=""
if [ -f "$rundir/board.md" ]; then
  board_branches="$(awk -F'|' '
    function clean(s) { gsub(/^[ \t]+|[ \t]+$/, "", s); if (s ~ /^`.*`$/) s = substr(s, 2, length(s) - 2); return s }
    { sub(/\r$/, "") }
    /^\|/ {
      if (!hdr) { for (i = 2; i < NF; i++) col[clean($i)] = i; hdr = 1; next }
      if ($0 ~ /^\|[ \t]*:?-/ || !("Branch" in col)) next
      b = clean($(col["Branch"])); if (b != "" && b != "-") print b
    }' "$rundir/board.md")"
fi
targets=" $epic "
for b in $board_branches; do targets="$targets$b "; done
run_wt="$(norm "$main/.claude/worktrees/$run")"
main_n="$(norm "$main")"

# Linked worktrees as path TAB branch (empty when detached), main checkout excluded.
wts="$(git worktree list --porcelain | tr -d '\r' | awk '
  /^worktree / { if (p != "") print p "\t" b; p = substr($0, 10); b = "" }
  /^branch refs\/heads\// { b = substr($0, 19) }
  END { if (p != "") print p "\t" b }')"

keep=" "          # branches left with a skipped worktree
remain=""         # path TAB branch of worktrees that stay
while IFS=$'\t' read -r path br; do
  [ -n "$path" ] || continue
  pn="$(norm "$path")"
  [ "$pn" != "$main_n" ] || { remain="$remain$path"$'\t'"$br"$'\n'; continue; }
  hit=0
  case "$targets" in *" $br "*) [ -n "$br" ] && hit=1 ;; esac
  [ "$pn" = "$run_wt" ] && hit=1
  if [ "$hit" -eq 0 ]; then remain="$remain$path"$'\t'"$br"$'\n'; continue; fi
  [ -z "$br" ] || case "$targets" in *" $br "*) ;; *) targets="$targets$br " ;; esac
  if [ ! -d "$path" ]; then continue; fi        # gone already: prune drops the record
  if [ -n "$(git -C "$path" status --porcelain 2>/dev/null)" ]; then
    say "SKIP $path: dirty"; keep="$keep$br "; remain="$remain$path"$'\t'"$br"$'\n'; continue
  fi
  if [ "$dry" -eq 1 ]; then say "REMOVED worktree $path"; continue; fi
  if err="$(git worktree remove "$path" 2>&1)"; then
    say "REMOVED worktree $path"
  else
    say "SKIP $path: $(printf '%s' "$err" | tr -d '\r' | tail -n 1)"
    keep="$keep$br "; remain="$remain$path"$'\t'"$br"$'\n'
  fi
done <<<"$wts"

# --- branches ----------------------------------------------------------------------------------
for b in $targets; do
  [ "$b" != "$default" ] || continue
  case "$keep" in *" $b "*) continue ;; esac
  git rev-parse -q --verify "refs/heads/$b" >/dev/null 2>&1 || continue
  at="$(printf '%s' "$remain" | awk -F'\t' -v b="$b" '$2 == b { print $1; exit }')"
  if [ -n "$at" ]; then say "SKIP branch $b: checked out at $at"; continue; fi
  if [ "$dry" -eq 1 ]; then say "DELETED branch $b"; continue; fi
  if err="$(git branch -q -D "$b" 2>&1)"; then say "DELETED branch $b"
  else say "SKIP branch $b: $(printf '%s' "$err" | tr -d '\r' | tail -n 1)"; fi
done

if [ "$has_origin" -eq 1 ] && git ls-remote --exit-code --heads origin "$epic" >/dev/null 2>&1; then
  if [ "$dry" -eq 1 ]; then say "DELETED remote $epic"
  elif err="$(git push -q origin --delete "$epic" 2>&1)"; then say "DELETED remote $epic"
  else say "SKIP remote $epic: $(printf '%s' "$err" | tr -d '\r' | tail -n 1)"; fi
fi

# --- stale locks and preview pid files ---------------------------------------------------------
dead() { local p; p="$(tr -d '\r\n ' <"$1" 2>/dev/null)"; [ -n "$p" ] && ! kill -0 "$p" 2>/dev/null; }
for d in "$common/pad-locks/merge" "$common"/pad-locks/slots/*; do
  [ -f "$d/pid" ] && dead "$d/pid" || continue
  if [ "$dry" -eq 0 ] && ! rm -rf "$d"; then say "SKIP lock $d: cannot remove"; continue; fi
  say "REMOVED lock $d"
done
for f in "$common"/pad-locks/merge-waiting/*; do
  [ -f "$f" ] && dead "$f" || continue
  if [ "$dry" -eq 0 ] && ! rm -f "$f"; then say "SKIP lock $f: cannot remove"; continue; fi
  say "REMOVED lock $f"
done
for f in "$common"/pad-preview/*.pid; do
  [ -f "$f" ] && dead "$f" || continue
  if [ "$dry" -eq 0 ] && ! rm -f "$f" "${f%.pid}.log"; then say "SKIP pid $f: cannot remove"; continue; fi
  say "REMOVED pid $f"
done

[ "$dry" -eq 1 ] || git worktree prune

# --- run files ---------------------------------------------------------------------------------
if [ -d "$rundir" ]; then
  if [ "$skipped" -gt 0 ]; then
    say "SKIP run $rundir: kept until the skipped items are cleaned"
  else
    if [ "$dry" -eq 0 ] && ! rm -rf "$rundir"; then say "SKIP run $rundir: cannot remove"
    else say "REMOVED run $rundir"; fi
  fi
fi

if [ "$skipped" -gt 0 ]; then echo "CLEANUP PARTIAL $skipped skipped"; exit 1; fi
if [ "$dry" -eq 1 ]; then echo "CLEANUP OK $removed removed (dry run)"; else echo "CLEANUP OK $removed removed"; fi
