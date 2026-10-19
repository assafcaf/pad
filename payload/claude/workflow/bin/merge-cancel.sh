#!/usr/bin/env bash
# Stop a running merge drain cleanly: merge-cancel.sh --run <id>   (merge.sh --run <id> --cancel)
#
# Kills the drain found through <main>/.work/runs/<id>/merge-drain.pid and everything below it,
# removes the candidate worktrees (detached, path contains `pad-candidate`), aborts a merge left
# in progress in the epic worktree, and removes the merge lock and the pid file. The merge queue
# is left as it is. Prints `CANCELLED <id>`, or `CANCEL nothing running`.
set -uo pipefail
bin="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$bin/merge-lib.sh"

[ "${1:-}" = --run ] && [ -n "${2:-}" ] || { echo "usage: merge-cancel.sh --run <id>" >&2; exit 64; }
run="$2"

common="$(git rev-parse --git-common-dir 2>/dev/null)" || { echo "ERROR $run: not in a git repository"; exit 2; }
common="$(cd "$common" && pwd)"
main="$(cd "$common/.." && pwd)"
dir="$main/.work/runs/$run"
wt="$main/.claude/worktrees/$run"
pidf="$dir/merge-drain.pid"

pid="$(cat "$pidf" 2>/dev/null)"
if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
  rm -f "$pidf"
  echo "CANCEL nothing running"
  exit 0
fi

kill_tree "$pid"
for _ in $(seq 1 100); do kill -0 "$pid" 2>/dev/null || break; sleep 0.1; done

# Candidate worktrees.
git -C "$main" worktree list --porcelain | sed -n 's/^worktree //p' | while IFS= read -r p; do
  case "$p" in
    *pad-candidate*)
      git -C "$main" worktree remove --force "$p" >/dev/null 2>&1
      rm -rf "$p" ;;
  esac
done
git -C "$main" worktree prune >/dev/null 2>&1

# A merge left in progress in the epic worktree.
if [ -d "$wt" ] && git -C "$wt" rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1; then
  git -C "$wt" merge --abort >/dev/null 2>&1
fi

# The lock, if the killed drain held it, and the files it leaves.
lock="$common/pad-locks/merge"
[ "$(cat "$lock/pid" 2>/dev/null)" = "$pid" ] && rm -rf "$lock"
rm -rf "$dir/merge-queue.lock"
rm -f "$pidf"
echo "CANCELLED $run"
