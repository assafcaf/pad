#!/usr/bin/env bash
# Triage a red heavy run without a blind revert.
#
#   triage.sh --run <id> --head <H> --base <sha> --landed K1=<merge sha>[,K2=<merge sha>...]
#             --ids <test id>...
#
# Run from the epic worktree. H is the epic head the heavy tier failed at, <sha> the head before
# K1 landed, and --landed lists K1..Kn in landing order with each ticket's merge commit. Every run
# is `pad-test.sh --role gate --ids <the failed ids>` in a side worktree of its own (removed on
# exit), so the epic worktree and its landing are never touched until the one revert at the end.
#
#   1. the failed ids at H, alone, in a fresh process: green -> `FLAKY`, stop.
#   2. the failed ids at <sha>: red -> `ENV` (not the batch's doing), stop, nothing is reverted.
#   3. halve K1..Kn by running at their merge commits (green at <sha>, red at Kn) until one ticket
#      is the first whose merge is red.
#   4. revert that ticket's merge with the `revert-merge` move (`git revert -m 1 <sha>`) in the
#      epic worktree and print `REJECTED <KEY>: heavy <ids>`.
#
# Exit 0 after any verdict, 2 when a run did not run or the arguments are unusable.

set -uo pipefail

bin="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  echo "usage: triage.sh --run <id> --head <H> --base <sha> --landed K1=<sha>[,K2=<sha>...] --ids <test id>..." >&2
  exit 2
}

run=""; head=""; base=""; landed=""; ids=()
while [ $# -gt 0 ]; do
  case "$1" in
    --run) run="${2:-}"; shift 2 ;;
    --head) head="${2:-}"; shift 2 ;;
    --base) base="${2:-}"; shift 2 ;;
    --landed) landed="${2:-}"; shift 2 ;;
    --ids)
      shift
      while [ $# -gt 0 ]; do
        case "$1" in --*) break ;; esac
        ids+=("$1"); shift
      done ;;
    *) usage ;;
  esac
done
[ -n "$run" ] && [ -n "$head" ] && [ -n "$base" ] && [ -n "$landed" ] && [ "${#ids[@]}" -gt 0 ] || usage

keys=(); merges=()
for pair in $(printf '%s' "$landed" | tr ',' ' '); do
  keys+=("${pair%%=*}"); merges+=("${pair#*=}")
done
n="${#keys[@]}"
[ "$n" -gt 0 ] || usage

side="$(mktemp -d)" || exit 2
trap 'git worktree remove --force "$side/wt" >/dev/null 2>&1; rm -rf "$side"' EXIT
git worktree add -q --detach "$side/wt" "$head" >/dev/null 2>&1 || { echo "triage.sh: cannot check out $head" >&2; exit 2; }

# red_at <commit>: 0 when the failed ids fail there, 1 when they pass; exits 2 when the run did not run.
red_at() {
  local rc out
  git -C "$side/wt" checkout -q --detach "$1" || { echo "triage.sh: cannot check out $1" >&2; exit 2; }
  out="$(cd "$side/wt" && bash "$bin/pad-test.sh" --run "$run" --ticket triage --role gate --ids "${ids[@]}" 2>&1)"; rc=$?
  case "$rc" in
    0) return 1 ;;
    1) return 0 ;;
    *) printf '%s\n' "$out" | tail -n 5 >&2; echo "triage.sh: the run at $1 did not run (exit $rc)" >&2; exit 2 ;;
  esac
}

if ! red_at "$head"; then echo "FLAKY"; exit 0; fi
if red_at "$base"; then echo "ENV"; exit 0; fi

# green at <base> (index 0), red at the last merge: the first red index is the cause.
lo=0; hi="$n"
while [ $((hi - lo)) -gt 1 ]; do
  mid=$(((lo + hi) / 2))
  if red_at "${merges[$((mid - 1))]}"; then hi="$mid"; else lo="$mid"; fi
done
culprit="${keys[$((hi - 1))]}"

if GIT_EDITOR=true git revert -m 1 --no-edit "${merges[$((hi - 1))]}" >/dev/null 2>&1; then
  echo "REJECTED $culprit: heavy ${ids[*]}"
else
  git revert --abort >/dev/null 2>&1
  echo "triage.sh: the revert of $culprit's merge failed" >&2
  exit 2
fi
