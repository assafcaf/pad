#!/usr/bin/env bash
# The merge engine: the one entry point for landing READY tickets.
#
#   merge.sh --run <id> --ready <KEY> <TASK_HEAD> <RED>   queue a ticket; drain the queue unless
#                                                         a drain is already running
#   merge.sh --run <id> --status                          QUEUE <n> / DRAIN running|idle / LAST ...
#   merge.sh --run <id> --cancel                          exec merge-cancel.sh --run <id>
#
# Run from any checkout of the repo; the run's files are <main checkout>/.work/runs/<id>/:
#   merge-queue       one `<KEY> <TASK_HEAD> <RED>` line per waiting ticket
#   merge-drain.pid   the pid of the running drain (removed when it exits)
#   merge-strategy    optional, `<name> [opt=val ...]`; read at the start of every pass
#   merge-last        the last finished pass, for --status
# The epic worktree is <main>/.claude/worktrees/<id>.
#
# A drain holds the merge lock (<git common dir>/pad-locks/merge) for its whole life and repeats
# until the queue is empty: choose the strategy (the run file, else the config's `Merge strategy:`
# line, else dynamic; dynamic with no run file runs batch; dynamic in the run file is an error),
# hand the pass's queue to the strategy script on stdin, then check the contract and print the
# result lines. The strategy gets PAD_RUN, PAD_EPIC_WORKTREE, PAD_EPIC_BRANCH, PAD_BIN,
# PAD_MERGE_LOCK_HELD and PAD_OPT_<NAME> per option. It prints one line per ticket:
# MERGED <KEY> <sha> | REJECTED <KEY>: .. | CONFLICT <KEY>: .. | ERROR <KEY>: .. | REQUEUE <KEY>.
#
# The contract after every pass: every ticket of the pass has a result line, and every commit the
# pass added to the epic branch is a `Merge <KEY>: ` commit of a ticket the strategy reported
# MERGED. Anything else prints `ERROR <KEY>: <what was broken>` and the exit code is 2.
#
# Exit 0, 2 on an error (an unknown sha or strategy, a broken contract), 64 usage.

set -uo pipefail

bin="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=merge-lib.sh
. "$bin/merge-lib.sh"

usage() { echo "usage: merge.sh --run <id> (--ready <KEY> <TASK_HEAD> <RED> | --status | --cancel)" >&2; exit 64; }

run=""; mode=""; pos=()
while [ $# -gt 0 ]; do
  case "$1" in
    --run) run="${2:-}"; shift 2 ;;
    --ready) mode=ready; shift ;;
    --status) mode=status; shift ;;
    --cancel) mode=cancel; shift ;;
    *) pos+=("$1"); shift ;;
  esac
done
[ -n "$run" ] && [ -n "$mode" ] || usage
[ "$mode" = cancel ] && exec bash "$bin/merge-cancel.sh" --run "$run"
if [ "$mode" = ready ]; then [ "${#pos[@]}" -eq 3 ] || usage; else [ "${#pos[@]}" -eq 0 ] || usage; fi

common="$(git rev-parse --git-common-dir 2>/dev/null)" || { echo "ERROR $run: not in a git repository"; exit 2; }
main="$(cd "$common/.." && pwd)"
common="$(cd "$common" && pwd)"
dir="$main/.work/runs/$run"
wt="$main/.claude/worktrees/$run"
queue="$dir/merge-queue"; pidf="$dir/merge-drain.pid"; runfile="$dir/merge-strategy"
last="$dir/merge-last"; qlock="$dir/merge-queue.lock"
mkdir -p "$dir"
cd "$main" || exit 2

alive() { [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null; }
drain_pid() { local p; p="$(cat "$pidf" 2>/dev/null)"; alive "$p" && printf '%s' "$p"; }
qcount() { grep -c '[^[:space:]]' "$queue" 2>/dev/null || true; }

# The queue mutex: a short mkdir lock; one whose owner is gone is reclaimed.
qtake() {
  local o
  until mkdir "$qlock" 2>/dev/null; do
    o="$(cat "$qlock/pid" 2>/dev/null)"
    if [ -n "$o" ] && ! alive "$o"; then rm -rf "$qlock"; continue; fi
    sleep 0.05
  done
  echo $$ > "$qlock/pid"
}
qdrop() { rm -rf "$qlock"; }

if [ "$mode" = status ]; then
  n="$(qcount)"; echo "QUEUE ${n:-0}"
  if [ -n "$(drain_pid)" ]; then echo "DRAIN running"; else echo "DRAIN idle"; fi
  if [ -s "$last" ]; then head -n 1 "$last" | tr -d '\r'; else echo "LAST none"; fi
  exit 0
fi

key="${pos[0]}"; thead="${pos[1]}"; red="${pos[2]}"
for s in "$thead" "$red"; do
  git cat-file -e "$s^{commit}" 2>/dev/null || { echo "ERROR $key: unknown sha $s"; exit 2; }
done

mine=""
qtake
printf '%s %s %s\n' "$key" "$thead" "$red" >> "$queue"
if [ -n "$(drain_pid)" ]; then
  qdrop; echo "QUEUED $key"; exit 0
fi
echo $$ > "$pidf"; mine=1
qdrop

# ---- the drain ----
lock=""; tmp="$(mktemp -d)"; rc=0
cleanup() {
  [ -z "$lock" ] || { [ "$(cat "$lock/pid" 2>/dev/null)" = "$$" ] && rm -rf "$lock"; }
  [ "$(cat "$pidf" 2>/dev/null)" = "$$" ] && rm -f "$pidf"
  [ "$(cat "$qlock/pid" 2>/dev/null)" = "$$" ] && rm -rf "$qlock"
  rm -rf "$tmp"
}
trap cleanup EXIT
trap 'exit 143' TERM INT

mkdir -p "$common/pad-locks"
lock="$(take_merge_lock "$common/pad-locks/merge")"

# A bin directory whose merge-gate.sh, merge-task.sh and merge-ticket.sh count the gates run.
shim="$tmp/bin"; mkdir -p "$shim"; gates_file="$tmp/gates"; : > "$gates_file"
for f in "$bin"/*.sh; do
  b="$(basename "$f")"
  case "$b" in
    merge-gate.sh) c='echo g >> "$PAD_GATES_FILE"' ;;
    merge-task.sh|merge-ticket.sh) c='case " $* " in *" --expect-tree "*) ;; *) echo g >> "$PAD_GATES_FILE";; esac' ;;
    *) c=':' ;;
  esac
  printf '#!/usr/bin/env bash\n%s\nexec bash "%s" "$@"\n' "$c" "$f" > "$shim/$b"
done
export PAD_GATES_FILE="$gates_file"

# choose: sets strat_name, strat_script, strat_opts (array) or strat_err.
choose() {
  local line out rc
  strat_err=""; strat_opts=()
  line="$(head -n 1 "$runfile" 2>/dev/null | tr -d '\r')"
  line="${line#"${line%%[![:space:]]*}"}"
  if [ -n "$line" ]; then
    if [ "${line%% *}" = dynamic ]; then strat_err="dynamic is reserved: the orchestrator picks a concrete strategy for the run file"; return; fi
    out="$(bash "$bin/merge-strategies.sh" resolve "$line")"; rc=$?
  else
    out="$(bash "$bin/merge-strategies.sh" resolve)"; rc=$?
    if [ "$rc" -eq 0 ] && [ "$(printf '%s' "$out" | head -n 1)" = dynamic ]; then
      line=batch; out="$(bash "$bin/merge-strategies.sh" resolve batch)"; rc=$?
    fi
  fi
  if [ "$rc" -ne 0 ]; then strat_err="$(printf '%s' "$out" | tr '\n' ' ')"; return; fi
  strat_script="$(printf '%s\n' "$out" | head -n 1)"
  strat_name="$(bash "$bin/merge-strategies.sh" list | awk -F'\t' -v s="$strat_script" '$2 == s { print $1; exit }')"
  while IFS= read -r o; do [ -n "$o" ] && strat_opts+=("$o"); done <<<"$(printf '%s\n' "$out" | tail -n +2)"
}

while :; do
  # Take the pass, or finish: the check and the pid-file removal are atomic with a --ready.
  qtake
  if ! grep -q '[^[:space:]]' "$queue" 2>/dev/null; then
    rm -f "$pidf"; qdrop; break
  fi
  choose
  cp "$queue" "$tmp/pass"; : > "$queue"
  qdrop
  tr -d '\r' < "$tmp/pass" | sed '/^[[:space:]]*$/d' > "$tmp/pass.in"
  keys="$(awk '{print $1}' "$tmp/pass.in")"

  if [ -n "$strat_err" ]; then
    while IFS= read -r k; do echo "ERROR $k: $strat_err"; done <<<"$keys"
    rc=2; continue
  fi

  before="$(git -C "$wt" rev-parse HEAD 2>/dev/null)"
  wtbranch="$(git -C "$wt" branch --show-current 2>/dev/null)"
  : > "$tmp/out"; : > "$gates_file"
  env PAD_RUN="$run" PAD_EPIC_WORKTREE="$wt" PAD_EPIC_BRANCH="$wtbranch" PAD_BIN="$shim" \
      PAD_MERGE_LOCK_HELD="$$" "${strat_opts[@]}" \
      bash "$strat_script" < "$tmp/pass.in" > "$tmp/out" 2>"$tmp/err"
  tr -d '\r' < "$tmp/out" > "$tmp/res"
  after="$(git -C "$wt" rev-parse HEAD 2>/dev/null)"

  # The commits the pass added to the epic branch, by key.
  : > "$tmp/commits"
  if [ "$before" != "$after" ]; then
    git -C "$wt" log --first-parent --format='%H %s' "$before..$after" > "$tmp/commits" 2>/dev/null
  fi
  stray=""
  while IFS= read -r c; do
    [ -n "$c" ] || continue
    subj="${c#* }"; ck=""
    if [[ "$subj" =~ ^Merge\ ([^:[:space:]]+):\  ]]; then ck="${BASH_REMATCH[1]}"; fi
    if [ -n "$ck" ] && grep -Fxq -- "$ck" <<<"$keys" && grep -q "^MERGED $ck " "$tmp/res"; then
      :
    else
      stray=1
    fi
  done < "$tmp/commits"

  merged=0; rejected=0; conflict=0; errs=0
  : > "$tmp/requeue"; : > "$tmp/print"
  while IFS= read -r k; do
    res="$(grep -E "^(MERGED|REJECTED|CONFLICT|ERROR|REQUEUE) $k([: ]|\$)" "$tmp/res" | head -n 1)"
    if [ -z "$res" ]; then
      echo "ERROR $k: the strategy left no result line for this ticket" >> "$tmp/print"; errs=$((errs + 1)); continue
    fi
    case "$res" in
      MERGED*)
        sha="${res##* }"
        if ! grep -Eq "^$sha Merge $k: " "$tmp/commits"; then
          echo "ERROR $k: reported MERGED but no Merge commit from merge-task.sh is on the epic branch for it" >> "$tmp/print"
          errs=$((errs + 1))
        else
          echo "$res" >> "$tmp/print"; merged=$((merged + 1))
        fi ;;
      REJECTED*) echo "$res" >> "$tmp/print"; rejected=$((rejected + 1)) ;;
      CONFLICT*) echo "$res" >> "$tmp/print"; conflict=$((conflict + 1)) ;;
      ERROR*) echo "$res" >> "$tmp/print"; errs=$((errs + 1)) ;;
      REQUEUE*) grep -E "^$k " "$tmp/pass.in" >> "$tmp/requeue" ;;
    esac
  done <<<"$keys"
  if [ -n "$stray" ] && [ "$errs" -eq 0 ]; then
    while IFS= read -r k; do echo "ERROR $k: the epic branch gained a commit that did not come from merge-task.sh for this pass" >> "$tmp/print"; done <<<"$keys"
    errs=1
  fi
  [ "$errs" -eq 0 ] || rc=2
  cat "$tmp/print"

  if [ -s "$tmp/requeue" ]; then
    qtake; cat "$tmp/requeue" "$queue" > "$tmp/q2" 2>/dev/null; cp "$tmp/q2" "$queue"; qdrop
  fi
  printf 'LAST %s merged=%s rejected=%s conflict=%s gates=%s\n' "$strat_name" "$merged" "$rejected" \
    "$conflict" "$(grep -c . "$gates_file")" > "$last"
done
exit "$rc"
