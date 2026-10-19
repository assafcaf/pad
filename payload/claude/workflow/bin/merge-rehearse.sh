#!/usr/bin/env bash
# Rehearse a merge strategy in a scratch repo with fixture gates.
#
#   merge-rehearse.sh <strategy name>        (also: merge-strategies.sh rehearse <name>)
#
# Builds a scratch repo (a bare origin, a main checkout with a scratch config, an epic worktree)
# and drives the real merge engine, merge.sh, with the named strategy through three passes:
#
#   green-batch   two independent tickets: both must land
#   conflict      two tickets editing one file: the first lands, the second is a CONFLICT
#   red-ticket    a ticket whose merged tree fails the gate: REJECTED, and it never lands
#   contract      every commit the passes added to the epic branch is a `Merge <KEY>: ` commit
#
# The gate is a fixture command (it fails when src/BAD exists), the lint is `true`: the real gate
# command is never run. The engine's own contract check prints `ERROR <KEY>: ...` for a strategy
# that lands any other way (a plain `git merge`); that line is printed here and fails the step.
# PAD_STRATEGIES_DIR is passed through, so a repo's own strategy folder is rehearsed too.
#
# Prints `STEP <name> PASS|FAIL <detail>` per step, then `REHEARSAL OK` (exit 0) or
# `REHEARSAL FAILED <n>` (exit 1, n = the FAIL lines). The scratch repo is always removed.

set -uo pipefail

[ $# -eq 1 ] && [ -n "$1" ] || { echo "usage: merge-rehearse.sh <strategy name>" >&2; exit 64; }
name="$1"
bin="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! bash "$bin/merge-strategies.sh" list | cut -f1 | grep -Fxq -- "$name"; then
  echo "ERROR $name: no strategy of that name"
  echo "REHEARSAL FAILED unknown strategy $name"
  exit 1
fi

fails=0
pass() { echo "STEP $1 PASS ${2:-}"; }
fail() { echo "STEP $1 FAIL ${2:-}"; fails=$((fails + 1)); }
last() { printf '%s\n' "$1" | tr -d '\r' | grep -v '^[[:space:]]*$' | tail -n 1; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

export GIT_AUTHOR_NAME=rehearsal GIT_AUTHOR_EMAIL=rehearsal@example.invalid
export GIT_COMMITTER_NAME=rehearsal GIT_COMMITTER_EMAIL=rehearsal@example.invalid
export PAD_LEDGER_ADAPTER=local

origin="$tmp/origin.git"
main="$tmp/main"
task="$tmp/task"
run=RH
wt="$main/.claude/worktrees/$run"
runs="$main/.work/runs/$run"

m() { git -C "$main" -c commit.gpgsign=false "$@"; }
t() { git -C "$task" -c commit.gpgsign=false "$@"; }
e() { git -C "$wt" -c commit.gpgsign=false "$@"; }

# --- scratch repo ------------------------------------------------------------------------------
setup_scratch() {
  git init -q --bare "$origin" &&
  git init -q "$main" &&
  m config commit.gpgsign false &&
  m config core.autocrlf false &&
  m remote add origin "$origin" &&
  mkdir -p "$main/.claude/workflow" "$main/src" "$main/tests" &&
  printf '.work/\n.claude/worktrees/\n' >"$main/.gitignore" &&
  printf 'base\n' >"$main/src/shared.txt" &&
  printf 'fixture\n' >"$main/tests/README.txt" &&
  cat >"$main/.claude/workflow/config.md" <<'EOF'
# Scratch config for merge-rehearse.sh

## Commands

| Command | Value |
|---|---|
| Setup in a fresh worktree | none |
| Full suite | `test ! -e src/BAD` |
| Lint | `true` |
| Typecheck | none |
| Test paths | `tests/` |
| Derived files | none |
| Dependency directory | none |
EOF
  m add -A && m commit -q -m "base" &&
  m branch -M main &&
  m push -q origin main 2>&1 &&
  mkdir -p "$main/.claude/worktrees" &&
  m worktree add -q -b "epic/$run" "$wt" HEAD &&
  e push -q -u origin "epic/$run" 2>&1 &&
  m worktree add -q --detach "$task" HEAD &&
  mkdir -p "$runs/tickets" "$main/.work/tickets/RH"
}
if out="$(setup_scratch 2>&1)"; then
  pass scratch-repo "bare origin, main checkout, epic worktree"
else
  fail scratch-repo "$(last "$out")"
  echo "REHEARSAL FAILED $fails"; exit 1
fi
printf '%s\n' "$name" >"$runs/merge-strategy"

base="$(e rev-parse HEAD)"

# mk <KEY> <green file> <content> [<other owned file>]: a ticket branch from the epic head with a
# red commit (a test file) and a green commit (the green file); sets $mk_head and $mk_red.
mk() {
  local key="$1" file="$2" content="$3" owns="$2"
  t checkout -q --detach "$(e rev-parse HEAD)" || return 1
  printf 'red\n' >"$task/tests/$key.txt"
  t add -- "tests/$key.txt" && t commit -q -m "test($key): rehearsal [red]" || return 1
  mk_red="$(t rev-parse HEAD)"
  mkdir -p "$(dirname "$task/$file")"
  printf '%s\n' "$content" >"$task/$file"
  t add -- "$file" && t commit -q -m "feat($key): rehearsal" || return 1
  mk_head="$(t rev-parse HEAD)"
  printf -- '---\nkey: %s\ntitle: "Rehearsal ticket %s"\nstatus: doing\n---\n\n## Outcomes\n- [O1] rehearsal\n\n## Owns\n- tests/%s.txt\n- %s\n\n## Touches\nnone\n\n## Protected\nno\n' \
    "$key" "$key" "$key" "$owns" >"$runs/tickets/$key.md"
  cp "$runs/tickets/$key.md" "$main/.work/tickets/RH/$key.md"
}

# drive <KEY HEAD RED>...: queue all but the last, hand the last to the engine, which drains the
# queue as one pass; sets $out and $rc.
drive() {
  local i
  : >"$runs/merge-queue"
  for ((i = 1; i + 3 <= $#; i += 3)); do
    printf '%s %s %s\n' "${!i}" "${@:i+1:1}" "${@:i+2:1}" >>"$runs/merge-queue"
  done
  local n=$(($# - 2))
  out="$(cd "$main" && bash "$bin/merge.sh" --run "$run" --ready "${@:n:3}" 2>&1)"; rc=$?
  out="$(printf '%s\n' "$out" | tr -d '\r')"
  printf '%s\n' "$out" | grep '^ERROR ' || true
}

merge_subjects() { e log --first-parent --format='%s' "$base..HEAD" 2>/dev/null; }
has() { printf '%s\n' "$out" | grep -Eq "$1"; }

# --- green-batch -------------------------------------------------------------------------------
if mk RH-T1 src/RH-T1.txt one && a_head="$mk_head" a_red="$mk_red" &&
  mk RH-T2 src/RH-T2.txt two; then
  b_head="$mk_head"; b_red="$mk_red"
  drive RH-T1 "$a_head" "$a_red" RH-T2 "$b_head" "$b_red"
  if [ "$rc" -ne 0 ]; then fail green-batch "exit $rc: $(last "$out")"
  elif ! has '^MERGED RH-T1 ' || ! has '^MERGED RH-T2 '; then fail green-batch "both tickets were not reported MERGED: $(last "$out")"
  elif ! merge_subjects | grep -q '^Merge RH-T1: ' || ! merge_subjects | grep -q '^Merge RH-T2: '; then
    fail green-batch "no Merge commit for each ticket on the epic branch"
  elif ! e cat-file -e HEAD:src/RH-T1.txt 2>/dev/null || ! e cat-file -e HEAD:src/RH-T2.txt 2>/dev/null; then
    fail green-batch "a ticket's file is not in the epic tree"
  else
    pass green-batch "two tickets merged"
  fi
else
  fail green-batch "cannot build the ticket branches"
fi

# --- conflict ----------------------------------------------------------------------------------
if mk RH-T3 src/shared.txt "from T3" && x_head="$mk_head" x_red="$mk_red" &&
  mk RH-T4 src/shared.txt "from T4"; then
  y_head="$mk_head"; y_red="$mk_red"
  drive RH-T3 "$x_head" "$x_red" RH-T4 "$y_head" "$y_red"
  if [ "$rc" -ne 0 ]; then fail conflict "exit $rc: $(last "$out")"
  elif ! has '^MERGED RH-T3 '; then fail conflict "the first ticket was not merged: $(last "$out")"
  elif ! has '^CONFLICT RH-T4'; then fail conflict "the second ticket was not reported CONFLICT: $(last "$out")"
  elif merge_subjects | grep -q '^Merge RH-T4: '; then fail conflict "the conflicting ticket landed"
  elif [ "$(e show HEAD:src/shared.txt 2>/dev/null | tr -d '\r')" != "from T3" ]; then fail conflict "the epic tree lost the first ticket's change"
  else
    pass conflict "first ticket merged, second reported CONFLICT"
  fi
else
  fail conflict "cannot build the ticket branches"
fi

# --- red-ticket --------------------------------------------------------------------------------
if mk RH-T5 src/BAD "fails the fixture gate"; then
  drive RH-T5 "$mk_head" "$mk_red"
  if [ "$rc" -ne 0 ]; then fail red-ticket "exit $rc: $(last "$out")"
  elif ! has '^REJECTED RH-T5'; then fail red-ticket "the red ticket was not reported REJECTED: $(last "$out")"
  elif merge_subjects | grep -q '^Merge RH-T5: ' || e cat-file -e HEAD:src/BAD 2>/dev/null; then
    fail red-ticket "the red ticket landed"
  else
    pass red-ticket "rejected, nothing landed"
  fi
else
  fail red-ticket "cannot build the ticket branch"
fi

# --- contract ----------------------------------------------------------------------------------
bad="$(merge_subjects | grep -v '^Merge RH-T[0-9]*: ' | head -n 1)"
count="$(merge_subjects | grep -c '^Merge RH-T[0-9]*: ')"
if [ -n "$bad" ]; then
  fail contract "the epic branch gained a commit that is not a ticket's merge: $bad"
elif [ "$count" -ne 3 ]; then
  fail contract "expected 3 merge commits on the epic branch, found $count"
else
  pass contract "every commit on the epic branch is a ticket's merge commit"
fi

if [ "$fails" -eq 0 ]; then echo "REHEARSAL OK"; exit 0; fi
echo "REHEARSAL FAILED $fails"; exit 1
