#!/usr/bin/env bash
# Merge a submitted task into the epic branch only after its merged tree passes the gate.
#
#   merge-task.sh --worktree <epic worktree> --branch <epic branch> [--setup "<cmd>"]
#                 --gate "<cmd>" --lint "<cmd>" [--typecheck "<cmd>"] [--test-paths "<pathspecs>"]
#                 [--derived "<path>=<cmd>" ...] [--affected "<cmd with {tests}>"]
#                 [--workers <n>] [--protected "<globs>"] [--ticket <path>]
#                 [--run <id> [--outcomes "<ids>"]] <KEY> <RED> <TASK_HEAD> "<GOAL>"
#
# Order: merge lock -> task-submit.sh -> git merge --no-ff --no-commit -> setup (only when a
# dependency manifest or lockfile changed) -> gate -> typecheck -> lint -> commit "Merge <KEY>: <GOAL>" -> push
# -u origin <branch>. Setup, gate and lint run with the epic worktree as their working directory.
# A failure before the commit aborts the merge, so the epic head and tree are exactly as they were.
#
# The merge lock `<git common dir>/pad-locks/merge` (a mkdir lock holding the owner's pid) is held
# from before the submission checks until exit, so concurrent merges on one repo run one after the
# other, each on the head the previous one produced. The gate runs through
# `suite-slot.sh --priority merge`. A gate whose failures (pytest-style `FAILED <file>::<test>`
# lines) all sit in test files the task neither changed nor imports is rerun once; a green rerun
# counts. A failure naming no test file is not rerun.
#
# --derived "<path>=<cmd>" (repeatable) names a file every task may change that is rebuilt rather
# than merged: a count in a README, a lockfile. When the merge conflicts only in derived files,
# each takes the epic's copy, then, after setup, its command runs in the epic worktree on the
# merged tree and the result is staged; the gate proves it. A conflict in any other path, or a
# command that fails, is CONFLICT as before. Every merge turns on `rerere.enabled`, so a
# resolution an owner records while rebasing is replayed the next time the same conflict comes.
#
# --affected "<cmd>" is gate=affected: affected-tests.sh selects the test files the task's change
# reaches, and the gate runs <cmd> with {tests} replaced by them; when it answers FULL, the full
# --gate runs instead. Either way one line says which: `gate: affected (<files>)` or
# `gate: full (<reason>)`. --workers <n> replaces {workers} in --gate and --affected, the host's
# test-worker budget (e.g. `pytest -n {workers}`).
#
# The gate runs as a child whose whole process tree is killed when this script exits early (a
# signal, a timeout), and a merge left in progress is aborted, so no orphaned workers keep
# running and the epic worktree is left as it was.
#
# --ticket <path> passes the ticket to task-submit.sh, which rejects a change outside its
# Owns and Touches. --protected "<globs>" (space or comma separated, the config's Protected
# paths) rejects, as `REJECTED <KEY>: needs-strict (...)`, a diff that touches a protected path
# when its red commit carries no `PAD-Role: test-designer` trailer.
#
# --run <id> writes the bookkeeping once the merge is pushed, so no agent does: the evidence file
# and run-log line through render-evidence.sh (its PR-table row is printed), a `REMOVALS <KEY>:`
# line (printed and logged) naming each test the merge removed and the rule that explains it,
# and the ticket to done through ledger.sh with the run's board.md row (branch, merge sha,
# evidence path).
# --outcomes "<ids>" fills the evidence's outcome column (default `-`). A bookkeeping write that
# fails prints `BOOKKEEPING FAIL <KEY>: <what>` and is logged with run-log.sh to be made again
# before the PR; it never turns the merge into a failure: the last line is still MERGED.
#
# Last line: MERGED <sha> | REJECTED <KEY>: <reason> | CONFLICT <KEY>: <paths> | ERROR <KEY>: ...
# Exit 0 MERGED, 1 REJECTED or CONFLICT, 2 infrastructure failure (push, dirty tree), 64 usage.
# A failed push keeps the gated merge commit locally: push it again, don't re-merge.

set -uo pipefail

usage() {
  echo "usage: merge-task.sh --worktree <epic worktree> --branch <epic branch> [--setup \"<cmd>\"] --gate \"<cmd>\" --lint \"<cmd>\" [--typecheck \"<cmd>\"] [--protected \"<globs>\"] [--ticket <path>] [--run <id> [--outcomes \"<ids>\"]] [--test-paths \"<pathspecs>\"] [--derived \"<path>=<cmd>\" ...] [--affected \"<cmd>\"] [--workers <n>] <KEY> <RED> <TASK_HEAD> \"<GOAL>\"" >&2
  exit 64
}

wt=""; branch=""; setup=""; gate=""; lint=""; typecheck=""; paths="tests/"
run=""; outcomes=""; protected=""; ticket=""
derived=()
affected=""
workers=""
pos=()
while [ $# -gt 0 ]; do
  case "$1" in
    --worktree) wt="${2:-}"; shift 2 ;;
    --branch) branch="${2:-}"; shift 2 ;;
    --setup) setup="${2:-}"; shift 2 ;;
    --gate) gate="${2:-}"; shift 2 ;;
    --lint) lint="${2:-}"; shift 2 ;;
    --typecheck) typecheck="${2:-}"; shift 2 ;;
    --run) run="${2:-}"; shift 2 ;;
    --outcomes) outcomes="${2:-}"; shift 2 ;;
    --protected) protected="${2:-}"; shift 2 ;;
    --ticket) ticket="${2:-}"; shift 2 ;;
    --test-paths) paths="${2:-}"; shift 2 ;;
    --derived) derived+=("${2:-}"); shift 2 ;;
    --affected) affected="${2:-}"; shift 2 ;;
    --workers) workers="${2:-}"; shift 2 ;;
    *) pos+=("$1"); shift ;;
  esac
done
[ "${#pos[@]}" -eq 4 ] && [ -n "$wt" ] && [ -n "$branch" ] && [ -n "$gate" ] && [ -n "$lint" ] ||
  usage
key="${pos[0]}"; red="${pos[1]}"; head="${pos[2]}"; goal="${pos[3]}"
if [ -n "$workers" ]; then
  gate="${gate//\{workers\}/$workers}"
  affected="${affected//\{workers\}/$workers}"
fi

bin="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
g() { git -C "$wt" "$@"; }
infra() { echo "ERROR $key: $1"; exit 2; }
log="$(mktemp)"
lock=""
stopped=()
# Start again every preview this merge stopped, whether the merge landed or was rejected.
restart_previews() {
  local s
  for s in ${stopped[@]+"${stopped[@]}"}; do
    bash "$bin/preview.sh" start --surface "$s" --worktree "$wt" >/dev/null 2>&1
  done
  stopped=()
}
gate_pid=""
merging=""
# descendants <pid>: every process below <pid>, deepest last.
descendants() {
  local c
  for c in $(ps -ef 2>/dev/null | awk -v p="$1" '$3 == p { print $2 }'); do
    echo "$c"
    descendants "$c"
  done
}
# kill_tree <pid>: <pid> and everything below it. On Windows the native processes (python.exe
# and its workers) are killed through taskkill /T as well.
kill_tree() {
  local p="$1" all w
  [ -n "$p" ] || return 0
  all="$p $(descendants "$p")"
  if command -v taskkill >/dev/null 2>&1; then
    for w in $all; do
      [ -r "/proc/$w/winpid" ] && taskkill //F //T //PID "$(cat "/proc/$w/winpid")" >/dev/null 2>&1
    done
  fi
  kill -KILL $all 2>/dev/null
  return 0
}
cleanup() {
  kill_tree "$gate_pid"
  [ -z "$merging" ] || abort
  rm -f "$log"
  restart_previews
  [ -z "$lock" ] || rm -rf "$lock"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# The merge lock, taken before anything reads the epic worktree. A lock whose owner is gone is
# reclaimed; one with no pid yet is being taken.
common="$(g rev-parse --git-common-dir 2>/dev/null)" &&
  common="$(cd "$wt" && cd "$common" && pwd)" || infra "$wt is not a git worktree"
mkdir -p "$common/pad-locks" || infra "cannot create $common/pad-locks"
until mkdir "$common/pad-locks/merge" 2>/dev/null; do
  owner="$(cat "$common/pad-locks/merge/pid" 2>/dev/null)"
  if [ -n "$owner" ] && ! kill -0 "$owner" 2>/dev/null; then
    rm -rf "$common/pad-locks/merge"
    continue
  fi
  sleep 0.1
done
lock="$common/pad-locks/merge"
echo $$ > "$lock/pid"

# Infrastructure: the epic worktree must be on its branch with no uncommitted tracked change.
[ "$(g symbolic-ref -q --short HEAD 2>/dev/null)" = "$branch" ] ||
  infra "$wt is not on branch $branch"
g rev-parse -q --verify MERGE_HEAD >/dev/null && infra "a merge is already in progress in $wt"
[ -z "$(g status --porcelain --untracked-files=no)" ] || infra "epic worktree $wt is dirty"
before="$(g rev-parse HEAD)"
g config rerere.enabled true >/dev/null 2>&1 || true

# derived_cmd <path>: the rebuild command --derived names for <path>; false when none does.
derived_cmd() {
  local d
  for d in ${derived[@]+"${derived[@]}"}; do
    [ "${d%%=*}" = "$1" ] && { printf '%s' "${d#*=}"; return 0; }
  done
  return 1
}

# Submission rules, before the tree is touched. A task cut from an earlier epic head is checked
# against the head it was cut from; the merge below then finds any conflict.
base="$(g merge-base "$before" "$head" 2>/dev/null)" || base="$before"
submit=(--test-paths "$paths")
[ -z "$ticket" ] || submit+=(--ticket "$ticket")
out="$(cd "$wt" && bash "$bin/task-submit.sh" "$base" "$red" "$head" "${submit[@]}" 2>&1)"
if [ $? -ne 0 ]; then
  reason="$(printf '%s\n' "$out" | tail -n 1)"
  echo "REJECTED $key: ${reason#SUBMIT FAIL }"
  exit 1
fi

# The protected-path guard: a diff touching a protected glob needs a red commit a test-designer
# wrote, which it marks with a `PAD-Role: test-designer` trailer. `*` matches across `/` here,
# which errs toward asking for the strict discipline.
if [ -n "$protected" ]; then
  hit=""
  set -f
  for f in $(g diff --name-only "$base" "$head"); do
    for p in ${protected//,/ }; do
      # shellcheck disable=SC2254
      case "$f" in $p|${p#\*\*/}) hit="$f"; break 2 ;; esac
    done
  done
  set +f
  if [ -n "$hit" ] &&
    ! g log -1 --format=%B "$red" 2>/dev/null | grep -qE '^PAD-Role:[[:space:]]*test-designer[[:space:]]*$'; then
    echo "REJECTED $key: needs-strict ($hit is a protected path; the red commit ${red:0:7} has no PAD-Role: test-designer trailer)"
    exit 1
  fi
fi

abort() { merging=""; g merge --abort >/dev/null 2>&1 || g reset -q --merge >/dev/null 2>&1; }

rebuild=()
merging=1
if ! g merge --no-ff --no-commit "$head" >"$log" 2>&1; then
  conflicts="$(g diff --name-only --diff-filter=U | tr '\n' ' ')"
  only_derived=1
  for c in $conflicts; do derived_cmd "$c" >/dev/null || only_derived=0; done
  if [ -n "$conflicts" ] && [ "$only_derived" -eq 1 ]; then
    # Take the epic's copy now; its command rebuilds it once setup has run.
    for c in $conflicts; do
      { g checkout -q --ours -- "$c" && g add -- "$c"; } || {
        abort; echo "CONFLICT $key: $c (could not take the epic's copy)"; exit 1; }
      rebuild+=("$c")
    done
  else
    abort
    if [ -n "$conflicts" ]; then
      echo "CONFLICT $key: ${conflicts% }"
      exit 1
    fi
    tail -n 40 "$log"
    infra "git merge failed without a conflict"
  fi
fi

# Print the failed step's tail, abort the merge and reject.
reject_step() {
  tail -n 40 "$log"
  abort
  echo "REJECTED $key: $1 failed (exit $2)"
  exit 1
}

# Run one step in the epic worktree; reject on failure.
step() {
  (cd "$wt" && bash -c "$2") >"$log" 2>&1 && return 0
  reject_step "$1" "$?"
}

# The gate, holding a suite slot ahead of task-side runs, as a child whose tree the exit trap
# can kill.
run_gate() {
  local rc
  (cd "$wt" && bash "$bin/suite-slot.sh" --priority merge -- bash -c "$gate_cmd") >"$log" 2>&1 &
  gate_pid=$!
  wait "$gate_pid"; rc=$?
  gate_pid=""
  return "$rc"
}

# True when the gate output names failing test files and every one is outside the task: not
# changed between <base> and the task head, and importing none of the changed files.
outside_only() {
  local files changed f c stem
  files="$(sed -n 's/^FAILED \([^ :]*\)::.*/\1/p' "$log" | sort -u)"
  [ -n "$files" ] || return 1
  changed="$(g diff --name-only "$base" "$head")"
  for f in $files; do
    printf '%s\n' "$changed" | grep -qxF "$f" && return 1
    [ -f "$wt/$f" ] || return 1
    for c in $changed; do
      stem="$(basename "$c")"
      [ -n "${stem%.*}" ] || continue
      stem="$(printf '%s' "${stem%.*}" | sed 's/[][\.*^$+?(){}|/]/\\&/g')"
      grep -E '(^|[^[:alnum:]_])(import|from|require|include|use)([^[:alnum:]_]|$)' "$wt/$f" |
        grep -qE "(^|[^[:alnum:]_])${stem}([^[:alnum:]_]|$)" && return 1
    done
  done
  return 0
}

# A running preview whose restart trigger this merge touches is stopped before setup, so it can't
# lock files setup replaces; the exit trap starts it again. A preview that is not running stays so.
changed_files="$(g diff --cached --name-only "$before")"
while IFS=$'\t' read -r surf triggers; do
  [ -n "$surf" ] || continue
  bash "$bin/preview.sh" status --surface "$surf" --worktree "$wt" 2>/dev/null |
    tail -n 1 | grep -q '^PREVIEW running ' || continue
  hit=""
  for t in ${triggers//,/ }; do
    t="${t%/}"
    printf '%s\n' "$changed_files" | grep -qE "^$(printf '%s' "$t" | sed 's/[][\.*^$+?(){}|/]/\\&/g')(/|$)" && hit=1
  done
  [ -n "$hit" ] || continue
  bash "$bin/preview.sh" stop --surface "$surf" --worktree "$wt" >/dev/null 2>&1
  stopped+=("$surf")
done <<<"$(bash "$bin/preview.sh" list --worktree "$wt" 2>/dev/null)"

if [ -n "$setup" ]; then
  manifests='^(.*/)?(package\.json|package-lock\.json|npm-shrinkwrap\.json|yarn\.lock|pnpm-lock\.yaml|bun\.lockb|requirements[^/]*\.txt|pyproject\.toml|poetry\.lock|uv\.lock|Pipfile|Pipfile\.lock|setup\.py|setup\.cfg|go\.mod|go\.sum|Cargo\.toml|Cargo\.lock|Gemfile|Gemfile\.lock|composer\.json|composer\.lock)$'
  if g diff --cached --name-only "$before" | grep -Eq "$manifests"; then
    step setup "$setup"
  fi
fi
for c in ${rebuild[@]+"${rebuild[@]}"}; do
  (cd "$wt" && bash -c "$(derived_cmd "$c")") >"$log" 2>&1
  rc=$?
  if [ "$rc" -ne 0 ] || grep -q '^<<<<<<< ' "$wt/$c" 2>/dev/null; then
    tail -n 40 "$log"
    abort
    echo "CONFLICT $key: $c (rebuild failed: exit $rc)"
    exit 1
  fi
  g add -- "$c"
done

gate_cmd="$gate"
if [ -n "$affected" ]; then
  pick="$(cd "$wt" && bash "$bin/affected-tests.sh" "$base" "$head" --test-paths "$paths" | tail -n 1)"
  case "$pick" in
    "TESTS "*) gate_cmd="${affected//\{tests\}/${pick#TESTS }}"
               echo "gate: affected (${pick#TESTS })" ;;
    *) echo "gate: full (${pick#FULL })" ;;
  esac
fi
run_gate; code=$?
if [ "$code" -ne 0 ] && outside_only; then
  echo "gate failed only in test files outside $key; rerunning it once"
  run_gate; code=$?
fi
[ "$code" -eq 0 ] || reject_step gate "$code"
[ -z "$typecheck" ] || step typecheck "$typecheck"
step lint "$lint"

g commit -q --no-edit -m "Merge $key: $goal" >"$log" 2>&1 || {
  tail -n 40 "$log"; abort; infra "git commit failed"; }
merging=""
sha="$(g rev-parse HEAD)"

g push -q -u origin "$branch" >"$log" 2>&1 || {
  tail -n 40 "$log"
  infra "push failed; merge $sha is committed locally on $branch"
}

# Bookkeeping, now that the merge is on origin. Failures are reported, never fatal.
if [ -n "$run" ]; then
  bk_fail() {
    echo "BOOKKEEPING FAIL $key: $1"
    (cd "$wt" && bash "$bin/run-log.sh" "$run" "BOOKKEEPING FAIL $key: $1 (merge ${sha:0:7})") >/dev/null 2>&1
  }
  green="${gate_cmd} -> pass"
  [ -z "$typecheck" ] || green="$green; $typecheck -> pass"
  out="$(cd "$wt" && bash "$bin/render-evidence.sh" --run "$run" --key "$key" --red "$red"     --merge "$sha" --outcomes "${outcomes:--}" --red-result "red commit ${red:0:7} checked by task-submit.sh"     --green-result "$green" 2>&1)" && printf '%s
' "$out" || bk_fail "evidence: $(printf '%s' "$out" | tail -n 1)"
  # The tests this merge removed, each with the rule that explains it, for the PR body.
  removals="$(cd "$wt" && bash "$bin/weakened-tests.sh" "$base" "$head" 2>/dev/null |
    sed -n '/^weakened-tests: removed tests explained by rules:/,/^weakened-tests: [^r]/p' |
    sed -n 's/^  \(.*\)/\1/p' | tr -s ' ' | paste -sd ';' - | sed 's/;/; /g')"
  if [ -n "$removals" ]; then
    echo "REMOVALS $key: $removals"
    (cd "$wt" && bash "$bin/run-log.sh" "$run" "REMOVALS $key: $removals") >/dev/null 2>&1 ||
      bk_fail "run-log: REMOVALS line"
  fi
  out="$(cd "$wt" && bash "$bin/ledger.sh" "$key" status done "merged ${sha:0:7} into $branch (run $run)"     --run "$run" --branch "$branch" --sha "${sha:0:7}" --evidence ".work/runs/$run/$key.md" 2>&1)" ||
    bk_fail "ledger: $(printf '%s' "$out" | tail -n 1)"
fi

echo "MERGED $sha"
