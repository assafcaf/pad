#!/usr/bin/env bash
# The host library behind every contained test run: memory in use, the cap, containment, the
# sweep of leftovers. Bash, git and the OS's own tools only. Run it, or source it for its
# functions (pp_*): `pad-proc.sh <verb> ...`
#
#   mem-in-use            machine memory in use, GB. The probe is PAD_MEMORY_PROBE (a shell
#                         command printing a number), else the OS's own. Exit 2 with a reason when
#                         it fails: there is no silent uncapped run.
#   cap                   the memory cap, GB: PAD_MEMORY_CAP (`<n>%` or `<n>GB`) over `Memory cap:`
#                         in host.md, else 85% of total memory.
#   total                 total memory, GB.   cores   the core count.
#   contain --run <id> --role <role> [--name <n>] [--peak-file <f>] -- <cmd...>
#                         runs cmd contained and recorded under <main>/.work/runs/<id>/pad-test/
#                         (<n>.meta, <n>.pids, <n>.done); exits with cmd's code, or, when
#                         cap-watch.sh killed it, prints `CAP KILLED <id> at <GB>` and exits 75.
#                         Windows: a job object through pad-proc.ps1 (peak memory included);
#                         elsewhere: a process group. Peak GB lands in <n>.peak.
#   kill <pids-file>      kills every process recorded there, and their descendants.
#   victim                the held run cap-watch.sh would kill next (its record name), or nothing.
#   peak <peak-file>      prints the peak GB a contained run recorded.
#   sweep                 kills processes recorded under finished runs and prints
#                         `SWEPT <n> processes, <GB>` when it killed any.
#   self-test             proves containment on this host: a run's detached grandchild must die
#                         with the run. Prints `SELF-TEST containment ok <job-object|process-group>`.
#
# host.md is <worktree>/.claude/workflow/host.md, else the main checkout's, or PAD_HOST_MD.
# Exit: 0 ok, 1 self-test failed, 2 memory probe or environment unavailable, 64 usage.

pp_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

pp_win() { case "$(uname -s 2>/dev/null)" in MINGW*|MSYS*|CYGWIN*) return 0 ;; esac; return 1; }

# pp_fmt <n>: a number with at most 2 decimals and no trailing zeros.
pp_fmt() {
  awk -v v="$1" 'BEGIN { s = sprintf("%.2f", v); sub(/0+$/, "", s); sub(/\.$/, "", s); print s }'
}

pp_isnum() { case "$1" in ''|*[!0-9.]*|*.*.*|.) return 1 ;; esac; return 0; }

# pp_le <a> <b>: a <= b.
pp_le() { awk -v a="$1" -v b="$2" 'BEGIN { exit !(a <= b + 0.0000001) }'; }

pp_main() {
  local top
  top="$(git rev-parse --show-toplevel 2>/dev/null)" || return 1
  (cd "$top" && cd "$(git rev-parse --git-common-dir)/.." && pwd)
}

pp_host_md() {
  local top main
  if [ -n "${PAD_HOST_MD:-}" ]; then [ -f "$PAD_HOST_MD" ] && echo "$PAD_HOST_MD"; return 0; fi
  top="$(git rev-parse --show-toplevel 2>/dev/null)" || return 0
  if [ -f "$top/.claude/workflow/host.md" ]; then echo "$top/.claude/workflow/host.md"; return 0; fi
  main="$(pp_main)" && [ -f "$main/.claude/workflow/host.md" ] && echo "$main/.claude/workflow/host.md"
  return 0
}

# pp_hostval <file> <key>: the value after `Key:`.
pp_hostval() { sed -n "s/^$2:[[:space:]]*//p" "$1" | head -n 1 | tr -d '\r'; }

pp_cores() {
  local n="${PAD_CORES:-}"
  [ -n "$n" ] || n="$(nproc 2>/dev/null)"
  [ -n "$n" ] || n="${NUMBER_OF_PROCESSORS:-}"
  [ -n "$n" ] || n="$(sysctl -n hw.ncpu 2>/dev/null)"
  pp_isnum "$n" || n=1
  echo "$n"
}

# pp_total_gb: PAD_MEMORY_TOTAL_GB, else `Memory total:` of host.md, else the machine's.
pp_total_gb() {
  local hm v
  if [ -n "${PAD_MEMORY_TOTAL_GB:-}" ]; then pp_fmt "$PAD_MEMORY_TOTAL_GB"; return 0; fi
  hm="$(pp_host_md)"
  if [ -n "$hm" ]; then
    v="$(pp_hostval "$hm" 'Memory total' | awk '{print $1}')"
    if pp_isnum "$v"; then pp_fmt "$v"; return 0; fi
  fi
  if [ -r /proc/meminfo ]; then
    v="$(awk '/^MemTotal:/ { print $2 / 1048576 }' /proc/meminfo)"
  elif v="$(sysctl -n hw.memsize 2>/dev/null)" && [ -n "$v" ]; then
    v="$(awk -v b="$v" 'BEGIN { print b / 1073741824 }')"
  else
    v="$(powershell.exe -NoProfile -Command '(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB' 2>/dev/null | tr -d '\r')"
  fi
  if ! pp_isnum "$v"; then echo "pad-proc: cannot read total memory on this host" >&2; return 2; fi
  pp_fmt "$v"
}

# pp_cap: the cap, GB.
pp_cap() {
  local spec="${PAD_MEMORY_CAP:-}" hm total
  if [ -z "$spec" ]; then
    hm="$(pp_host_md)"
    [ -n "$hm" ] && spec="$(pp_hostval "$hm" 'Memory cap')"
  fi
  [ -n "$spec" ] || spec="85%"
  case "$spec" in
    *%)
      total="$(pp_total_gb)" || return 2
      pp_fmt "$(awk -v p="${spec%\%}" -v t="$total" 'BEGIN { print p / 100 * t }')" ;;
    *)
      spec="${spec%[Gg][Bb]}"; spec="${spec%% *}"
      pp_isnum "$spec" || { echo "pad-proc: unreadable Memory cap '$spec'" >&2; return 2; }
      pp_fmt "$spec" ;;
  esac
}

# pp_mem_in_use: machine memory in use, GB. Exit 2 with a reason when it cannot be read.
pp_mem_in_use() {
  local out rc v
  if [ -n "${PAD_MEMORY_PROBE:-}" ]; then
    out="$(eval "$PAD_MEMORY_PROBE" 2>&1)"; rc=$?
    if [ "$rc" -ne 0 ]; then
      echo "pad-proc: memory probe failed (exit $rc): $out" >&2; return 2
    fi
    v="$(printf '%s\n' "$out" | tail -n 1 | tr -d '[:space:]')"
    pp_isnum "$v" || { echo "pad-proc: memory probe printed '$v', not a number" >&2; return 2; }
    pp_fmt "$v"; return 0
  fi
  if [ -r /proc/meminfo ]; then
    v="$(awk '/^MemTotal:/ {t=$2} /^MemAvailable:/ {a=$2} /^MemFree:/ {f=$2} /^Buffers:/ {b=$2} /^Cached:/ {c=$2}
              END { if (a == "") a = f + b + c; if (t > 0) print (t - a) / 1048576 }' /proc/meminfo)"
  elif command -v vm_stat >/dev/null 2>&1; then
    v="$(vm_stat | awk -v t="$(sysctl -n hw.memsize 2>/dev/null)" '
      /page size of/ { ps = $8 } /Pages (free|inactive|speculative):/ { gsub(/\./, "", $3); free += $3 }
      END { if (t > 0 && ps > 0) print (t - free * ps) / 1073741824 }')"
  fi
  if ! pp_isnum "$v"; then
    echo "pad-proc: no memory probe works on this host (set PAD_MEMORY_PROBE)" >&2; return 2
  fi
  pp_fmt "$v"
}

# --- processes -------------------------------------------------------------------------------

pp_alive() { [ -n "$1" ] && kill -0 "$1" 2>/dev/null; }

# pp_pairs: `pid ppid` lines of every process, from one `ps` call. (Git for Windows' `ps -eo`
# fails; its plain `ps` has the pid in column 1 and the parent in column 2.)
pp_pairs() {
  if pp_win; then
    ps 2>/dev/null | awk 'NR > 1 { print $1, $2 }'
  elif ! ps -eo pid=,ppid= 2>/dev/null; then
    ps 2>/dev/null | awk 'NR > 1 { print $1, $2 }'
  fi
}

# pp_starter: call it first thing in a script, before anything slow. Sets pp_starter_pid to the
# process that started it (empty when there is none this shell can see: parent pid 1, as on
# Windows when a native program started it) and pp_starter_dead to 1 when that process is already
# gone, so the script ends at once instead of outliving it.
pp_starter() {
  pp_starter_pid=""; pp_starter_dead=0
  case "$PPID" in ''|*[!0-9]*|0|1) return 0 ;; esac
  if pp_alive "$PPID"; then pp_starter_pid="$PPID"; else pp_starter_dead=1; fi
}

# pp_descendants <pid>...: every descendant pid of the given pids, one per line (one listing).
pp_descendants() {
  [ $# -gt 0 ] || return 0
  pp_pairs | awk -v roots="$*" '
    { kid[$2] = kid[$2] " " $1 }
    END { n = split(roots, r, " "); for (k = 1; k <= n; k++) isroot[r[k]] = 1
          for (k = 1; k <= n; k++) { m = 1; q[1] = r[k]
            for (i = 1; i <= m; i++) { c = split(kid[q[i]], a, " ")
              for (j = 1; j <= c; j++) if (!(a[j] in seen) && !(a[j] in isroot)) { seen[a[j]] = 1; q[++m] = a[j]; print a[j] } } } }'
}

# pp_kill_tree <pid>...: kill each pid and its descendants (one process listing for all of them);
# prints the number killed.
pp_kill_tree() {
  local p all="" n=0 k live=""
  for p in "$@"; do
    pp_alive "$p" && live="$live $p"
  done
  [ -n "$live" ] || { echo 0; return 0; }
  all="$live $(pp_descendants $live | tr '\n' ' ')"
  for k in $all; do
    if pp_alive "$k"; then kill -9 "$k" 2>/dev/null; n=$((n + 1)); fi
  done
  echo "$n"
}

# pp_pidfile_pids <file>: the distinct pids in a pid file (no process started).
pp_pidfile_pids() {
  local line out=" "
  [ -f "$1" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    case "$line" in ''|*[!0-9]*) continue ;; esac
    case "$out" in *" $line "*) ;; *) out="$out$line " ;; esac
  done < "$1"
  echo $out
}

pp_kill_pidfile() {
  local f="$1" pids p
  [ -f "$f" ] || return 0
  pids="$(pp_pidfile_pids "$f")"
  for p in $pids; do kill -9 -- "-$p" 2>/dev/null; done
  pp_kill_tree $pids
}

# --- the victim ------------------------------------------------------------------------------

# pp_rank <role>: kill order of a role (0 first); empty for a role that is never killed.
pp_rank() {
  case "$1" in
    agent|owner|test-designer) echo 0 ;;
    suite-owner) echo 1 ;;
    gate) echo 2 ;;
    *) echo "" ;;
  esac
}

# pp_victim_base [main]: the record (path without extension) cap-watch.sh would kill: a held run,
# lowest role rank first, then the newest start; empty when nothing is killable. Starts nothing.
pp_victim_base() {
  local main="${1:-}" meta base role="" start="" root r best="" bestr=0 beststart=0 line
  [ -n "$main" ] || main="$(pp_main)" || return 1
  for meta in "$main"/.work/runs/*/pad-test/*.meta; do
    [ -f "$meta" ] || continue
    base="${meta%.meta}"
    [ -f "$base.done" ] && continue
    [ -f "$base.killed" ] && continue
    role=""; start=""
    while IFS= read -r line || [ -n "$line" ]; do
      line="${line%$'\r'}"
      case "$line" in role=*) role="${line#role=}" ;; start=*) start="${line#start=}" ;; esac
    done < "$meta"
    r="$(pp_rank "$role")"
    [ -n "$r" ] || continue
    root=""
    read -r root < "$base.pids" 2>/dev/null
    root="${root%$'\r'}"
    pp_alive "$root" || continue
    # integers: nanoseconds fit in 64 bits
    start="${start//[!0-9]/}"; : "${start:=0}"
    if [ -z "$best" ] || [ "$r" -lt "$bestr" ] || { [ "$r" -eq "$bestr" ] && [ "$start" -gt "$beststart" ]; }; then
      best="$base"; bestr="$r"; beststart="$start"
    fi
  done
  echo "$best"
}

# --- containment -----------------------------------------------------------------------------

pp_job_object() { pp_win && command -v powershell.exe >/dev/null 2>&1 && [ "${PAD_CONTAIN:-}" != group ]; }

pp_contain_mode() { if pp_job_object; then echo job-object; else echo process-group; fi; }

pp_contain() {
  local run="" role="" name="" peakfile="" main dir pid sampler code gb base start host
  while [ $# -gt 0 ]; do
    case "$1" in
      --run) run="${2:-}"; shift 2 ;;
      --role) role="${2:-}"; shift 2 ;;
      --name) name="${2:-}"; shift 2 ;;
      --peak-file) peakfile="${2:-}"; shift 2 ;;
      --) shift; break ;;
      *) break ;;
    esac
  done
  if [ -z "$run" ] || [ -z "$role" ] || [ $# -eq 0 ]; then
    echo "usage: pad-proc.sh contain --run <id> --role <role> [--name <n>] [--peak-file <f>] -- <cmd...>" >&2
    return 64
  fi
  main="$(pp_main)" || { echo "pad-proc: not inside a git repository" >&2; return 2; }
  dir="$main/.work/runs/$run/pad-test"
  mkdir -p "$dir" || return 2
  start="$(date +%s%N 2>/dev/null)"
  case "$start" in *N*|'') start="$(date +%s)000000000" ;; esac
  [ -n "$name" ] || name="$role-$start-$$"
  rm -f "$dir/$name.done" "$dir/$name.killed" "$dir/$name.peak"
  printf 'run=%s\nrole=%s\nstart=%s\nhost=%s\n' "$run" "$role" "$start" "$$" > "$dir/$name.meta"
  : > "$dir/$name.pids"
  base="$(pp_mem_in_use 2>/dev/null)" || base=""

  if pp_job_object; then
    { printf '#!/usr/bin/env bash\nexec'; printf ' %q' "$@"; printf '\n'; } > "$dir/$name.run.sh"
    powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass \
      -File "$(cygpath -w "$pp_here/pad-proc.ps1")" job-run "$(cygpath -w "$(command -v bash)")" \
      "$(cygpath -w "$dir/$name.run.sh")" "$(cygpath -w "$dir/$name.jobpeak")" &
    pid=$!
  else
    set -m
    "$@" &
    pid=$!
    set +m
  fi
  echo "$pid" >> "$dir/$name.pids"

  host=$$
  # Sampler: records the run's descendants (the sweep's input) and a sampled peak.
  (
    peak=0
    while sleep "${PAD_SAMPLE_INTERVAL:-2}"; do
      pp_alive "$host" || exit 0
      pp_descendants "$pid" >> "$dir/$name.pids"
      cur="$(pp_mem_in_use 2>/dev/null)" || continue
      peak="$(awk -v p="$peak" -v c="$cur" 'BEGIN { print (c > p ? c : p) }')"
      printf '%s\n' "$peak" > "$dir/$name.samplepeak"
    done
  ) >/dev/null 2>&1 &
  sampler=$!

  trap 'kill -9 "$sampler" 2>/dev/null; pp_kill_pidfile "$dir/$name.pids" >/dev/null; echo 143 > "$dir/$name.done"; exit 143' TERM INT
  wait "$pid"
  code=$?
  trap - TERM INT
  kill -9 "$sampler" 2>/dev/null
  wait "$sampler" 2>/dev/null

  # Peak: the job object's when there is one, else the sampled rise over the starting level.
  if [ -f "$dir/$name.jobpeak" ]; then
    mv "$dir/$name.jobpeak" "$dir/$name.peak"
  elif [ -f "$dir/$name.samplepeak" ] && pp_isnum "$base"; then
    awk -v p="$(cat "$dir/$name.samplepeak")" -v b="$base" 'BEGIN { d = p - b; if (d < 0) d = 0; print d }' > "$dir/$name.peak"
  fi
  [ -n "$peakfile" ] && [ -f "$dir/$name.peak" ] && cp "$dir/$name.peak" "$peakfile"

  if [ -f "$dir/$name.killed" ]; then
    gb="$(cat "$dir/$name.killed")"
    echo "CAP KILLED $run at $gb"
    code=75
  fi
  pp_kill_pidfile "$dir/$name.pids" >/dev/null
  echo "$code" > "$dir/$name.done"
  return "$code"
}

pp_peak() { [ -f "${1:-}" ] && pp_fmt "$(cat "$1")" || echo 0; }

# --- the sweep -------------------------------------------------------------------------------

pp_sweep() {
  local main f base p n=0 k before after gb pids
  main="$(pp_main)" || { echo "pad-proc: not inside a git repository" >&2; return 2; }
  before="$(pp_mem_in_use 2>/dev/null)" || before=""
  for f in "$main"/.work/runs/*/pad-test/*.pids; do
    [ -f "$f" ] || continue
    base="${f%.pids}"
    [ -f "$base.done" ] || continue
    pids="$(pp_pidfile_pids "$f")"
    for p in $pids; do kill -9 -- "-$p" 2>/dev/null; done
    k="$(pp_kill_tree $pids)"
    n=$((n + k))
    mv "$f" "$f.swept"
  done
  [ "$n" -gt 0 ] || return 0
  sleep 1
  after="$(pp_mem_in_use 2>/dev/null)" || after=""
  gb=0
  if pp_isnum "$before" && pp_isnum "$after"; then
    gb="$(awk -v b="$before" -v a="$after" 'BEGIN { d = b - a; if (d < 0) d = 0; print d }')"
  fi
  echo "SWEPT $n processes, $(pp_fmt "$gb") GB"
}

# --- the self-test ---------------------------------------------------------------------------

pp_self_test() {
  local run="selftest-$$" main dir gp mode survivors="" i p
  main="$(pp_main)" || { echo "pad-proc: self-test needs a git repository" >&2; return 2; }
  dir="$main/.work/runs/$run/pad-test"
  mkdir -p "$dir" || return 2
  mode="$(pp_contain_mode)"
  gp="$dir/grandchild.pid"
  # The fixture: a child that starts a detached grandchild, then waits.
  printf '%s\n' '#!/usr/bin/env bash' \
    "nohup sleep 300 >/dev/null 2>&1 </dev/null &" \
    "echo \$! > '$gp'" \
    "sleep 300" > "$dir/fixture.sh"
  pp_contain --run "$run" --role self-test --name fixture -- bash "$dir/fixture.sh" >/dev/null 2>&1 &
  local wrapper=$!; disown "$wrapper" 2>/dev/null
  for i in $(seq 1 150); do [ -s "$gp" ] && break; sleep 0.2; done
  if [ ! -s "$gp" ]; then
    kill -9 "$wrapper" 2>/dev/null
    echo "SELF-TEST containment failed: the fixture never started ($mode)" >&2
    rm -rf "$main/.work/runs/$run"; return 1
  fi
  local gpid root
  gpid="$(tr -d '\r\n ' < "$gp")"
  root="$(head -n 1 "$dir/fixture.pids" 2>/dev/null)"
  # Kill the run: its recorded root, and nothing else. Containment must take the rest.
  if [ "$mode" = process-group ]; then kill -9 -- "-$root" 2>/dev/null; fi
  kill -9 "$root" 2>/dev/null
  kill -9 "$wrapper" 2>/dev/null
  for i in $(seq 1 50); do pp_alive "$gpid" || break; sleep 0.2; done
  pp_alive "$gpid" && survivors="$gpid"
  if [ -n "$survivors" ]; then
    kill -9 "$gpid" 2>/dev/null
    echo "SELF-TEST containment failed ($mode): survived the kill: pid $survivors (sleep 300)" >&2
    rm -rf "$main/.work/runs/$run"; return 1
  fi
  rm -rf "$main/.work/runs/$run"
  echo "SELF-TEST containment ok $mode"
}

pp_main_verbs() {
  local verb="${1:-}"
  [ $# -gt 0 ] && shift
  case "$verb" in
    mem-in-use) pp_mem_in_use ;;
    cap) pp_cap ;;
    total) pp_total_gb ;;
    cores) pp_cores ;;
    contain) pp_contain "$@" ;;
    kill) pp_kill_pidfile "${1:-}" >/dev/null ;;
    peak) pp_peak "${1:-}" ;;
    sweep) pp_sweep ;;
    self-test) pp_self_test ;;
    victim) local v; v="$(pp_victim_base)" || return 2; [ -z "$v" ] || echo "${v##*/}" ;;
    *) echo "usage: pad-proc.sh mem-in-use|cap|total|cores|contain|kill|victim|peak|sweep|self-test ..." >&2; return 64 ;;
  esac
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  pp_main_verbs "$@"
  exit $?
fi
