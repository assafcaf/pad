#!/usr/bin/env bash
# Helpers the merge scripts share; sourced, never run.
#   descendants <pid>, kill_tree <pid>, take_merge_lock <dir>, outside_only (needs g, wt, log,
#   base, head), MANIFESTS (the dependency manifests whose change triggers setup).

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
# take_merge_lock <dir>: wait for the mkdir lock <dir>, reclaiming one whose owner is gone (one
# with no pid yet is being taken), write this script's pid into it and print <dir>.
take_merge_lock() {
  local d="$1" owner
  until mkdir "$d" 2>/dev/null; do
    owner="$(cat "$d/pid" 2>/dev/null)"
    if [ -n "$owner" ] && ! kill -0 "$owner" 2>/dev/null; then
      rm -rf "$d"
      continue
    fi
    sleep 0.1
  done
  echo $$ > "$d/pid"
  printf '%s' "$d"
}

MANIFESTS='^(.*/)?(package\.json|package-lock\.json|npm-shrinkwrap\.json|yarn\.lock|pnpm-lock\.yaml|bun\.lockb|requirements[^/]*\.txt|pyproject\.toml|poetry\.lock|uv\.lock|Pipfile|Pipfile\.lock|setup\.py|setup\.cfg|go\.mod|go\.sum|Cargo\.toml|Cargo\.lock|Gemfile|Gemfile\.lock|composer\.json|composer\.lock)$'

# outside_only: true when the gate output names failing test files and every one is outside the task: not
# changed between <base> and the task head, and importing none of the changed files.
outside_only() {
  local files changed f c stem
  files="$(failed_ids | sed 's/::.*//' | sort -u)"
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

# Flake record: the tests that failed outside a change, per run, in the main checkout.
# flake_file <run> <dir>: <main checkout>/.work/runs/<run>/flakes, resolved from any worktree.
flake_file() {
  local common
  common="$(git -C "$2" rev-parse --git-common-dir 2>/dev/null)" &&
    common="$(cd "$2" && cd "$common" && pwd)" || return 1
  printf '%s' "$(cd "$common/.." && pwd)/.work/runs/$1/flakes"
}
# failed_ids: the ids of the failing tests the gate output in $log names. A failure is a line of
# the adapter's results vocabulary (`failure <id> ...`, `error <id> ...`, which pad-test.sh prints
# for a tier run); `FAILED <id> ...` is read for the gates whose command is the repo's own.
failed_ids() {
  sed -n -E 's/^(failure|error|FAILED) ([^ ]+).*/\2/p' "$log" | sort -u
}
# failed_tests: the failing ids that name one test (`<file>::<test>`).
failed_tests() {
  failed_ids | grep '::'
}
# flake_count <file> <test>: how many times <test> is recorded.
flake_count() {
  [ -f "$1" ] || { echo 0; return; }
  awk -v t="$2" '$1 == t { n++ } END { print n + 0 }' "$1"
}
# flake_record <file> <label>: append every failing test in $log as `<test> <label> <ts>`.
flake_record() {
  local t
  mkdir -p "$(dirname "$1")" 2>/dev/null
  for t in $(failed_tests); do
    printf '%s %s %s\n' "$t" "$2" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$1"
  done
}
# flake_known <file>: print the first failing test already recorded and its prior count; true if any.
flake_known() {
  local t n
  for t in $(failed_tests); do
    n="$(flake_count "$1" "$t")"
    [ "$n" -gt 0 ] && { echo "$t $n"; return 0; }
  done
  return 1
}

# Leak watch: the processes a gate step started and left alive. lw_start <pid> samples, one process
# listing a tick, everything below <pid> and, between ticks, polls the ones it has seen with
# builtins only: a process alive while the process that started it is gone is a leak the moment it
# is orphaned, even when a containment wrapper kills it a moment later. An orphan that is already
# dead counts only when the host recorded it as a process of the run: lw_stop <pid file>... names
# the host's pid files (the wrapper's helpers orphan themselves and end on their own, and are not
# recorded). lw_stop kills what is still alive, prints one `LEAK <pid> <command>` line per leaked
# process and cleans up.
lw_list() {
  ps -eo pid=,ppid=,args= 2>/dev/null ||
    ps -ef 2>/dev/null | awk 'NR > 1 { c = $6; for (i = 7; i <= NF; i++) c = c " " $i; print $2, $3, c }'
}
# lw_tree <pid>: `pid ppid command` of every process below <pid>.
lw_tree() {
  lw_list | awk -v root="$1" '
    { line[$1] = $0; kid[$2] = kid[$2] " " $1 }
    END { n = 1; q[1] = root
          for (i = 1; i <= n; i++) { c = split(kid[q[i]], a, " ")
            for (j = 1; j <= c; j++) if (!(a[j] in seen)) { seen[a[j]] = 1; q[++n] = a[j]; print line[a[j]] } } }'
}
lw_pid=""; lw_pid2=""; lw_dir=""; lw_root=""
lw_start() {
  lw_root="$1"
  lw_dir="$(mktemp -d)" || return 0
  : > "$lw_dir/known"; : > "$lw_dir/orphans"
  mkfifo "$lw_dir/nap" 2>/dev/null
  # The ticker: one listing a tick, the new processes appended to `known`.
  (
    seen=" "
    while :; do
      while read -r p q cmd; do
        case "$seen" in *" $p "*) continue ;; esac
        seen="$seen$p "
        printf '%s %s %s\n' "$p" "$q" "$cmd" >> "$lw_dir/known"
      done <<LW
$(lw_tree "$lw_root")
LW
      sleep 0.2
    done
  ) >/dev/null 2>&1 &
  lw_pid=$!
  # The poller: builtins only, so a listing in flight never delays it.
  (
    nap=0
    if [ -p "$lw_dir/nap" ] && exec 9<>"$lw_dir/nap"; then nap=1; fi
    kp=(); kq=(); done_n=0
    while :; do
      n=0
      while read -r p q _; do
        n=$((n + 1))
        [ "$n" -gt "$done_n" ] || continue
        kp+=("$p"); kq+=("$q")
      done < "$lw_dir/known"
      done_n="$n"
      for i in "${!kp[@]}"; do
        p="${kp[$i]}"
        [ -n "$p" ] || continue
        if ! kill -0 "$p" 2>/dev/null; then kp[$i]=""
        elif ! kill -0 "${kq[$i]}" 2>/dev/null; then echo "$p" >> "$lw_dir/orphans"; kp[$i]=""; fi
      done
      if [ "$nap" -eq 1 ]; then read -r -t 0.02 -u 9 _ 2>/dev/null || :; else sleep 0.05; fi
    done
  ) >/dev/null 2>&1 &
  lw_pid2=$!
}
lw_stop() {
  [ -n "$lw_pid" ] || return 0
  kill -9 "$lw_pid" "$lw_pid2" 2>/dev/null; wait "$lw_pid" "$lw_pid2" 2>/dev/null
  local p q cmd recorded i pending=""
  # Recorded by the host and orphaned or alive: a leak. Alive and unrecorded: given the wrapper's
  # own helpers' time to end (one sample interval), then a leak.
  : > "$lw_dir/leaks"
  while read -r p q cmd; do
    [ "$p" != "$lw_root" ] || continue
    recorded=0
    [ $# -eq 0 ] || ! grep -qxF "$p" "$@" 2>/dev/null || recorded=1
    if [ "$recorded" -eq 1 ] && { kill -0 "$p" 2>/dev/null || grep -qxF "$p" "$lw_dir/orphans"; }; then
      printf '%s %s\n' "$p" "$cmd" >> "$lw_dir/leaks"
    elif kill -0 "$p" 2>/dev/null; then
      pending="$pending $p"
    fi
  done < "$lw_dir/known"
  for ((i = 0; i < 100; i++)); do
    [ -n "$pending" ] || break
    p=""; for q in $pending; do kill -0 "$q" 2>/dev/null && p="$p $q"; done
    pending="$p"
    [ -n "$pending" ] || break
    [ "$i" -lt $(( ${PAD_SAMPLE_INTERVAL:-2} * 10 + 10 )) ] || break
    read -r -t 0.1 <> "$lw_dir/nap" 2>/dev/null || sleep 0.1
  done
  for p in $pending; do
    printf '%s %s\n' "$p" "$(awk -v p="$p" '$1 == p { $1 = ""; $2 = ""; sub(/^ +/, ""); print; exit }' "$lw_dir/known")" >> "$lw_dir/leaks"
  done
  awk '!s[$1]++' "$lw_dir/leaks" > "$lw_dir/leaks.u"; mv "$lw_dir/leaks.u" "$lw_dir/leaks"
  while read -r p cmd; do kill_tree "$p"; done < "$lw_dir/leaks"
  cat "$lw_dir/leaks"
  rm -rf "$lw_dir"; lw_pid=""; lw_pid2=""; lw_dir=""
}

