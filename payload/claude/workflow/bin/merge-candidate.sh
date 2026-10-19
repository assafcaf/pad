#!/usr/bin/env bash
# Build the combined tree of several READY tickets in a throwaway worktree.
#
#   merge-candidate.sh --worktree <epic worktree> --branch <epic branch> --run <id>
#                      [--deps <dir>] [--derived "<path>=<cmd>" ...] [--test-paths "<pathspecs>"]
#                      [--protected "<globs>"] <KEY>...
#   merge-candidate.sh --remove <path>
#
# Each KEY's `<KEY> <TASK_HEAD> <RED>` line is read from <main checkout>/.work/runs/<id>/merge-queue.
# The candidate is a detached worktree at the epic head (its path contains `pad-candidate`, under
# <git common dir>/pad-candidates) that links --deps (the config's Dependency directory) from the
# epic worktree; the epic worktree, its branch and origin are never touched.
#
# Prints CANDIDATE <path>, then per ticket, in order:
#   PREFIX <KEY> <commit> <tree>   the candidate after that ticket (a merge commit on the previous
#                                  prefix, or on the epic head for the first)
#   CONFLICT <KEY>: <paths>        the ticket conflicts with what was built; it is left out
#   REJECTED <KEY>: <reason>       a submission or protected-path check failed; it is left out
# The next ticket is tried on what exists so far. The submission and protected checks are
# merge-task.sh's, run before each ticket is merged. A conflict only in --derived files takes the
# epic's copy and rebuilds it with its command in the candidate, as merge-task.sh does.
# Exit 0 (even with CONFLICT or REJECTED lines), 2 infrastructure failure, 64 usage.
# --remove <path> removes a candidate (and unlinks its dependency directory); prints nothing.

set -uo pipefail

bin="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  echo "usage: merge-candidate.sh --worktree <epic worktree> --branch <epic branch> --run <id> [--deps <dir>] [--derived \"<path>=<cmd>\" ...] [--test-paths \"<pathspecs>\"] [--protected \"<globs>\"] <KEY>... | --remove <path>" >&2
  exit 64
}

# unlink_deps <candidate>: drop the dependency link before the worktree goes, so removing the
# worktree can never reach into the directory it points at.
unlink_deps() {
  local gd marker rel link
  gd="$(git -C "$1" rev-parse --git-dir 2>/dev/null)" || return 0
  gd="$(cd "$1" && cd "$gd" && pwd)"
  marker="$gd/pad-deps"
  [ -f "$marker" ] || return 0
  rel="$(cat "$marker")"
  link="$1/$rel"
  if [ -L "$link" ]; then rm -f "$link"
  elif [ -d "$link" ]; then
    if command -v cygpath >/dev/null 2>&1; then cmd //c rmdir "$(cygpath -w "$link")" >/dev/null 2>&1 || true
    else rmdir "$link" 2>/dev/null || true; fi
  fi
  rm -f "$marker"
}

if [ "${1:-}" = "--remove" ]; then
  [ $# -eq 2 ] || usage
  cand="$2"
  [ -d "$cand" ] || exit 0
  unlink_deps "$cand"
  git -C "$cand" worktree remove --force "$cand" >/dev/null 2>&1 || rm -rf "$cand"
  git -C "$cand/.." worktree prune >/dev/null 2>&1 || true
  exit 0
fi

wt=""; branch=""; run=""; deps=""; paths="tests/"; protected=""
derived=()
keys=()
while [ $# -gt 0 ]; do
  case "$1" in
    --worktree) wt="${2:-}"; shift 2 ;;
    --branch) branch="${2:-}"; shift 2 ;;
    --run) run="${2:-}"; shift 2 ;;
    --deps) deps="${2:-}"; shift 2 ;;
    --derived) derived+=("${2:-}"); shift 2 ;;
    --test-paths) paths="${2:-}"; shift 2 ;;
    --protected) protected="${2:-}"; shift 2 ;;
    -*) usage ;;
    *) keys+=("$1"); shift ;;
  esac
done
[ -n "$wt" ] && [ -n "$branch" ] && [ -n "$run" ] && [ "${#keys[@]}" -gt 0 ] || usage

g() { git -C "$wt" "$@"; }
infra() { echo "ERROR: $1"; exit 2; }

common="$(g rev-parse --git-common-dir 2>/dev/null)" &&
  common="$(cd "$wt" && cd "$common" && pwd)" || infra "$wt is not a git worktree"
main="$(g worktree list --porcelain | sed -n '1s/^worktree //p')"
queue="$main/.work/runs/$run/merge-queue"
[ -f "$queue" ] || infra "no merge queue at $queue"
epic_head="$(g rev-parse HEAD)" || infra "cannot read the epic head"

derived_cmd() {
  local d
  for d in ${derived[@]+"${derived[@]}"}; do
    [ "${d%%=*}" = "$1" ] && { printf '%s' "${d#*=}"; return 0; }
  done
  return 1
}

mkdir -p "$common/pad-candidates" || infra "cannot create $common/pad-candidates"
cand="$(mktemp -d "$common/pad-candidates/pad-candidate.XXXXXX")" || infra "cannot create a candidate directory"
cand="$(cd "$cand" && { pwd -W 2>/dev/null || pwd; })"
if ! g worktree add --detach --quiet "$cand" "$epic_head" >/dev/null 2>&1; then
  infra "could not create the candidate worktree at $cand"
fi
c() { git -C "$cand" "$@"; }

if [ -n "$deps" ]; then
  d="${deps%/}"
  src="$(cd "$wt" && pwd)/$d"
  if [ -d "$src" ]; then
    mkdir -p "$(dirname "$cand/$d")"
    linked=""
    if command -v cygpath >/dev/null 2>&1; then
      cmd //c mklink //J "$(cygpath -w "$cand/$d")" "$(cygpath -w "$src")" >/dev/null 2>&1 && linked=1
    else
      ln -s "$src" "$cand/$d" && linked=1
    fi
    if [ -n "$linked" ]; then
      gd="$(c rev-parse --git-dir)"; gd="$(cd "$cand" && cd "$gd" && pwd)"
      printf '%s' "$d" > "$gd/pad-deps"
    fi
  fi
fi
echo "CANDIDATE $cand"

abort() { c merge --abort >/dev/null 2>&1 || c reset -q --merge >/dev/null 2>&1; }

for key in "${keys[@]}"; do
  line="$(awk -v k="$key" '$1 == k { l = $0 } END { print l }' "$queue")"
  head="$(printf '%s' "$line" | awk '{print $2}')"
  red="$(printf '%s' "$line" | awk '{print $3}')"
  if [ -z "$head" ] || [ -z "$red" ]; then
    echo "REJECTED $key: not in the merge queue"
    continue
  fi
  base="$(c merge-base HEAD "$head" 2>/dev/null)" || base="$epic_head"
  out="$(cd "$cand" && bash "$bin/task-submit.sh" "$base" "$red" "$head" --test-paths "$paths" 2>&1)"
  if [ $? -ne 0 ]; then
    reason="$(printf '%s\n' "$out" | tail -n 1)"
    echo "REJECTED $key: ${reason#SUBMIT FAIL }"
    continue
  fi
  if [ -n "$protected" ]; then
    hit=""
    set -f
    for f in $(c diff --name-only "$base" "$head"); do
      for p in ${protected//,/ }; do
        # shellcheck disable=SC2254
        case "$f" in $p|${p#\*\*/}) hit="$f"; break 2 ;; esac
      done
    done
    set +f
    if [ -n "$hit" ] &&
      ! c log -1 --format=%B "$red" 2>/dev/null | grep -qE '^PAD-Role:[[:space:]]*test-designer[[:space:]]*$'; then
      echo "REJECTED $key: needs-strict ($hit is a protected path; the red commit ${red:0:7} has no PAD-Role: test-designer trailer)"
      continue
    fi
  fi

  rebuild=()
  if ! c merge --no-ff --no-commit "$head" >/dev/null 2>&1; then
    conflicts="$(c diff --name-only --diff-filter=U | tr '\n' ' ')"
    only_derived=1
    for f in $conflicts; do derived_cmd "$f" >/dev/null || only_derived=0; done
    if [ -n "$conflicts" ] && [ "$only_derived" -eq 1 ]; then
      for f in $conflicts; do
        { c checkout -q --ours -- "$f" && c add -- "$f"; } || {
          abort; echo "CONFLICT $key: $f (could not take the epic's copy)"; continue 2; }
        rebuild+=("$f")
      done
    else
      abort
      if [ -n "$conflicts" ]; then
        echo "CONFLICT $key: ${conflicts% }"
      else
        echo "REJECTED $key: git merge failed without a conflict"
      fi
      continue
    fi
  fi
  for f in ${rebuild[@]+"${rebuild[@]}"}; do
    (cd "$cand" && bash -c "$(derived_cmd "$f")") >/dev/null 2>&1
    rc=$?
    if [ "$rc" -ne 0 ] || grep -q '^<<<<<<< ' "$cand/$f" 2>/dev/null; then
      abort
      echo "CONFLICT $key: $f (rebuild failed: exit $rc)"
      continue 2
    fi
    c add -- "$f"
  done
  if ! c commit -q --no-edit -m "Merge $key: candidate" >/dev/null 2>&1; then
    abort
    echo "REJECTED $key: could not commit the candidate merge"
    continue
  fi
  echo "PREFIX $key $(c rev-parse HEAD) $(c rev-parse 'HEAD^{tree}')"
done
exit 0
