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

# Flake record: the tests that failed outside a change, per run, in the main checkout.
# flake_file <run> <dir>: <main checkout>/.work/runs/<run>/flakes, resolved from any worktree.
flake_file() {
  local common
  common="$(git -C "$2" rev-parse --git-common-dir 2>/dev/null)" &&
    common="$(cd "$2" && cd "$common" && pwd)" || return 1
  printf '%s' "$(cd "$common/.." && pwd)/.work/runs/$1/flakes"
}
# failed_tests: the test ids (`<file>::<test>`) the gate output in $log names.
failed_tests() {
  sed -n 's/^FAILED \([^ ]*::[^ ]*\).*/\1/p' "$log" | sort -u
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

