#!/usr/bin/env bash
# Run a full-suite command holding one of N suite slots, so parallel tasks can't overload the host.
#
#   suite-slot.sh [--priority merge] [--estimate-gb <n>] [--workers <n>] -- <cmd...>
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
# Admission (only when --estimate-gb or --workers is given; a bare run keeps the slots alone): once
# it holds its slots the run waits until machine memory in use (pad-proc.sh mem-in-use) plus its
# estimate is within the cap (pad-proc.sh cap), and the admitted runs' workers plus its own are
# within cores x the cap's share of total memory. It prints `CAP WAIT <in use>/<cap>` on stderr at
# once and then every PAD_CAP_WAIT_INTERVAL seconds (60), re-checking every half second. An
# estimate above the whole cap, or workers above the whole budget, start only when no other run
# is admitted. Admitted runs are marked by an `admitted` file (estimate, workers) in their slot
# dir, which the others count. An unreadable memory probe exits 2 with the reason.
#
# Exits with <cmd>'s exit code; 64 on usage, 2 outside a git repo.

set -uo pipefail

usage() { echo "usage: suite-slot.sh [--priority merge] [--estimate-gb <n>] [--workers <n>] -- <cmd...>" >&2; exit 64; }

priority=task
estimate=""
workers=""
while [ $# -gt 0 ]; do
  case "$1" in
    --priority) [ "${2:-}" = merge ] || usage; priority=merge; shift 2 ;;
    --estimate-gb) estimate="${2:-}"; case "$estimate" in ''|*[!0-9.]*) usage ;; esac; shift 2 ;;
    --workers) workers="${2:-}"; case "$workers" in ''|*[!0-9]*) usage ;; esac; shift 2 ;;
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

# admit: wait until the cap and the worker budget have room, then mark this run admitted.
admit() {
  # shellcheck source=pad-proc.sh
  . "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/pad-proc.sh"
  local cap total cores budget est wk interval last=0 now used n owk ok d p w lock="$locks/admit.lock"
  cap="$(pp_cap)" || exit 2
  total="$(pp_total_gb)" || exit 2
  cores="$(pp_cores)"
  budget="$(awk -v c="$cores" -v k="$cap" -v t="$total" 'BEGIN { print (t > 0 ? c * k / t : c) }')"
  est="${estimate:-0}"; wk="${workers:-0}"
  interval="${PAD_CAP_WAIT_INTERVAL:-60}"
  while :; do
    until mkdir "$lock" 2>/dev/null; do
      reap "$lock"
      sleep 0.05
    done
    echo $$ > "$lock/pid"
    used="$(pp_mem_in_use)" || { rm -rf "$lock"; exit 2; }
    # the other admitted runs, once each (a run holds a repo slot and maybe a host slot)
    n=0; owk=0
    for d in "$locks"/slots/*/; do
      [ -f "${d}admitted" ] || continue
      p="$(cat "${d}pid" 2>/dev/null)"
      [ -n "$p" ] && [ "$p" != "$$" ] && kill -0 "$p" 2>/dev/null || continue
      w="$(awk 'NR == 2' "${d}admitted")"
      n=$((n + 1)); owk=$((owk + ${w:-0}))
    done
    ok=1
    if ! pp_le "$(awk -v u="$used" -v e="$est" 'BEGIN { print u + e }')" "$cap"; then
      if pp_le "$est" "$cap" || [ "$n" -gt 0 ]; then ok=0; fi
    fi
    if [ "$wk" -gt 0 ] && [ "$n" -gt 0 ] &&
       ! pp_le "$(awk -v a="$owk" -v b="$wk" 'BEGIN { print a + b }')" "$budget"; then
      ok=0
    fi
    if [ "$ok" -eq 1 ]; then
      printf '%s\n%s\n' "$est" "$wk" > "$held/admitted"
      rm -rf "$lock"
      return 0
    fi
    rm -rf "$lock"
    now="$(date +%s)"
    if [ "$last" -eq 0 ] || [ $((now - last)) -ge "$interval" ]; then
      echo "CAP WAIT $used/$cap" >&2
      last="$now"
    fi
    sleep 0.5
  done
}
if [ -n "$estimate" ] || [ -n "$workers" ]; then admit; fi

"$@"
code=$?
exit "$code"
