#!/usr/bin/env bash
# Run a full-suite command holding one of N suite slots, so parallel tasks can't overload the host.
#
#   suite-slot.sh [--priority merge] -- <cmd...>
#
# Slots are directories `<git common dir>/pad-locks/slots/<i>` (mkdir is atomic everywhere; Git
# Bash has no flock), each holding the owner's pid, so a slot whose owner died is reclaimed.
# N comes from PAD_SUITE_SLOTS, else `Suite slots: <n>` in the repo's .claude/workflow/config.md,
# else 2. A `--priority merge` run marks itself waiting under pad-locks/merge-waiting/; while any
# merge run waits, task-side runs don't take a free slot.
#
# A host budget, shared by every repo on the machine, adds a second level: PAD_HOST_SLOTS, else
# `Host suite slots: <n>` in the config (none when unset). Its slot dirs `<i>` live under
# PAD_HOST_SLOTS_DIR, else ~/.pad/slots, are taken after the repo slot and released with it, and
# follow the same reclaim and merge-priority rules.
#
# Exits with <cmd>'s exit code; 64 on usage, 2 outside a git repo.

set -uo pipefail

usage() { echo "usage: suite-slot.sh [--priority merge] -- <cmd...>" >&2; exit 64; }

priority=task
while [ $# -gt 0 ]; do
  case "$1" in
    --priority) [ "${2:-}" = merge ] || usage; priority=merge; shift 2 ;;
    --) shift; break ;;
    *) usage ;;
  esac
done
[ $# -gt 0 ] || usage

common="$(git rev-parse --git-common-dir 2>/dev/null)" &&
  common="$(cd "$common" && pwd)" || { echo "suite-slot.sh: not inside a git repository" >&2; exit 2; }

cfg="$(git rev-parse --show-toplevel 2>/dev/null)/.claude/workflow/config.md"
num() { sed -n 's/.*[Ss]uite slots[^0-9]*\([0-9][0-9]*\).*/\1/p'; }

slots="${PAD_SUITE_SLOTS:-}"
if [ -z "$slots" ] && [ -f "$cfg" ]; then
  slots="$(grep -i 'suite slots' "$cfg" | grep -vi 'host suite slots' | head -n 1 | num)"
fi
case "$slots" in ''|*[!0-9]*) slots=2 ;; esac
[ "$slots" -ge 1 ] || slots=1

hslots="${PAD_HOST_SLOTS:-}"
if [ -z "$hslots" ] && [ -f "$cfg" ]; then
  hslots="$(grep -i 'host suite slots' "$cfg" | head -n 1 | num)"
fi
case "$hslots" in ''|*[!0-9]*) hslots=0 ;; esac
hostdir="${PAD_HOST_SLOTS_DIR:-$HOME/.pad/slots}"

locks="$common/pad-locks"
waiting="$locks/merge-waiting"
mkdir -p "$locks/slots" "$waiting"
if [ "$hslots" -ge 1 ]; then mkdir -p "$hostdir/merge-waiting" || hslots=0; fi

held=""
hheld=""
marker=""
hmarker=""
cleanup() {
  [ -n "$marker" ] && rm -f "$marker"
  [ -n "$hmarker" ] && rm -f "$hmarker"
  [ -n "$held" ] && rm -rf "$held"
  [ -n "$hheld" ] && rm -rf "$hheld"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# A lock dir whose recorded owner is gone is removed. A dir without a pid yet is being taken.
reap() {
  local pid
  pid="$(cat "$1/pid" 2>/dev/null)" || return 0
  [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null && rm -rf "$1"
}

# merge_waiting <dir>: is a live merge run marked waiting there?
merge_waiting() {
  local f pid
  for f in "$1"/*; do
    [ -e "$f" ] || continue
    pid="$(cat "$f" 2>/dev/null)"
    if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then rm -f "$f"; continue; fi
    return 0
  done
  return 1
}

# take <slots dir> <n>: take one of the n slot dirs and print its path.
take() {
  local i
  for i in $(seq 1 "$2"); do
    if mkdir "$1/$i" 2>/dev/null; then
      echo $$ > "$1/$i/pid"
      echo "$1/$i"
      return 0
    fi
    reap "$1/$i"
  done
  return 1
}

# acquire <slots dir> <n> <waiting dir>: wait for a slot and print its path. A task run leaves a
# free slot alone while a merge run waits.
acquire() {
  local got
  while :; do
    if [ "$priority" = merge ] || ! merge_waiting "$3"; then
      got="$(take "$1" "$2")" && { echo "$got"; return 0; }
    fi
    sleep 0.1
  done
}

if [ "$priority" = merge ]; then
  marker="$waiting/$$"
  echo $$ > "$marker"
fi
held="$(acquire "$locks/slots" "$slots" "$waiting")"
if [ -n "$marker" ]; then rm -f "$marker"; marker=""; fi

if [ "$hslots" -ge 1 ]; then
  if [ "$priority" = merge ]; then
    hmarker="$hostdir/merge-waiting/$$"
    echo $$ > "$hmarker"
  fi
  hheld="$(acquire "$hostdir" "$hslots" "$hostdir/merge-waiting")"
  if [ -n "$hmarker" ]; then rm -f "$hmarker"; hmarker=""; fi
fi

"$@"
code=$?
exit "$code"
