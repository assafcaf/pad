#!/usr/bin/env bash
# Summarise a run from the timestamped lines of its progress.md, from any worktree.
#
#   run-stats.sh --run <id>
#
# Reads <main checkout>/.work/runs/<id>/progress.md. A line counts when it is
#
#   <ISO 8601 timestamp> <event> [<KEY>] [free text]
#
# e.g. `2026-10-15T10:00:05Z dispatch E7-T1`, written with
# `run-log.sh <id> "$(date -u +%Y-%m-%dT%H:%M:%SZ) <event> <KEY> ..."`. The timestamp is
# YYYY-MM-DDTHH:MM[:SS[.fff]] with Z, ±HH:MM, ±HHMM or no zone (read as UTC). Events (case
# does not matter):
#
#   dispatch <KEY>       an owner was started on the ticket (again, after a replan)
#   READY <KEY> <sha>    the owner reported ready; every READY after the first is a rework round
#   MERGED <KEY> <sha>   the ticket landed on the epic branch
#   CONFLICT|REJECTED|FAILED|NEEDS_RULING <KEY> ...   the matching report or merge result
#   replan [<KEY>] ...   the orchestrator replanned
#   turn ...             one orchestrator turn (no key)
#
# Every other line (untimestamped, unknown event) is ignored, so progress.md can hold anything.
#
# Output, one `STAT <name> <value>` per line: turns, tickets (keys dispatched or merged), merged,
# open (dispatched, never merged), conflicts, rejections, failures, rulings, replans, rework
# (sum of READY - 1 per key), span_seconds (first to last timestamp), critical_path (the key with
# the longest dispatch-to-merge time; `-` when none merged; Depends-on is not read) and
# critical_path_seconds; then per key wall.<KEY> (first dispatch to last MERGED, seconds) and
# rework.<KEY> when above 0. Last line: `STATS <run> <tickets> tickets`.
#
# Exit 0; 1 when progress.md is missing (last line `STATS FAIL <run>: <why>`); 64 usage.

set -uo pipefail

usage() { echo "usage: run-stats.sh --run <id>" >&2; exit 64; }

[ $# -eq 2 ] && [ "$1" = --run ] && [ -n "$2" ] || usage
run="$2"

fail() { echo "STATS FAIL $run: $1"; exit 1; }

top="$(git rev-parse --show-toplevel 2>/dev/null)" || fail "not a git repository"
main="$(cd "$top" && cd "$(git rev-parse --git-common-dir)/.." && pwd)" || fail "cannot find the main checkout"
log="$main/.work/runs/$run/progress.md"
[ -f "$log" ] || fail "no progress log at $log"

awk -v run="$run" '
  # Days since 1970-01-01 for a proleptic Gregorian date (Howard Hinnant).
  function days(y, m, d,   era, yoe, mp, doy, doe) {
    y -= (m <= 2)
    era = int((y >= 0 ? y : y - 399) / 400)
    yoe = y - era * 400
    mp = (m + 9) % 12
    doy = int((153 * mp + 2) / 5) + d - 1
    doe = yoe * 365 + int(yoe / 4) - int(yoe / 100) + doy
    return era * 146097 + doe - 719468
  }
  # Seconds since the epoch for an ISO timestamp, or -1 when it is not one.
  function epoch(ts,   date, rest, zone, sign, zh, zm, t, n, hms, s) {
    if (ts !~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]/) return -1
    date = substr(ts, 1, 10); rest = substr(ts, 12)
    zone = 0
    if (rest ~ /Z$/) rest = substr(rest, 1, length(rest) - 1)
    else if (match(rest, /[+-][0-9][0-9]:?[0-9][0-9]$/)) {
      t = substr(rest, RSTART); rest = substr(rest, 1, RSTART - 1)
      sign = (substr(t, 1, 1) == "-") ? -1 : 1
      gsub(/[:+-]/, "", t)
      zone = sign * (substr(t, 1, 2) * 3600 + substr(t, 3, 2) * 60)
    }
    if (rest !~ /^[0-9][0-9]:[0-9][0-9](:[0-9][0-9](\.[0-9]+)?)?$/) return -1
    n = split(rest, hms, ":")
    s = (n >= 3) ? int(hms[3]) : 0
    return days(substr(date, 1, 4) + 0, substr(date, 6, 2) + 0, substr(date, 9, 2) + 0) * 86400 \
      + hms[1] * 3600 + hms[2] * 60 + s - zone
  }
  function see(k) { if (!(k in known)) { known[k] = 1; order[++nk] = k } }
  { sub(/\r$/, "") }
  {
    t = epoch($1)
    if (t < 0 || NF < 2) next
    if (first == "" || t < first) first = t
    if (last == "" || t > last) last = t
    ev = toupper($2); k = $3
    if (ev == "TURN") { turns++; next }
    if (ev == "REPLAN") { replans++; next }
    if (k == "") next
    if (ev == "DISPATCH") { see(k); if (!(k in start)) start[k] = t }
    else if (ev == "READY") { see(k); ready[k]++ }
    else if (ev == "MERGED") { see(k); merged_at[k] = t }
    else if (ev == "CONFLICT") conflicts++
    else if (ev == "REJECTED") rejections++
    else if (ev == "FAILED") failures++
    else if (ev == "NEEDS_RULING") rulings++
  }
  END {
    merged = 0; open = 0; rework = 0; cp = "-"; cps = 0
    for (i = 1; i <= nk; i++) {
      k = order[i]
      if (k in merged_at) merged++
      else if (k in start) open++
      if (ready[k] > 1) rework += ready[k] - 1
      if ((k in start) && (k in merged_at) && merged_at[k] >= start[k]) {
        wall[k] = merged_at[k] - start[k]
        if (cp == "-" || wall[k] > cps) { cp = k; cps = wall[k] }
      }
    }
    printf "STAT turns %d\n", turns
    printf "STAT tickets %d\n", nk
    printf "STAT merged %d\n", merged
    printf "STAT open %d\n", open
    printf "STAT conflicts %d\n", conflicts
    printf "STAT rejections %d\n", rejections
    printf "STAT failures %d\n", failures
    printf "STAT rulings %d\n", rulings
    printf "STAT replans %d\n", replans
    printf "STAT rework %d\n", rework
    printf "STAT span_seconds %d\n", (first == "" ? 0 : last - first)
    printf "STAT critical_path %s\n", cp
    printf "STAT critical_path_seconds %d\n", cps
    for (i = 1; i <= nk; i++) {
      k = order[i]
      if (k in wall) printf "STAT wall.%s %d\n", k, wall[k]
      if (ready[k] > 1) printf "STAT rework.%s %d\n", k, ready[k] - 1
    }
    printf "STATS %s %d tickets\n", run, nk
  }' "$log"
