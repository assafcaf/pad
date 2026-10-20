#!/usr/bin/env bash
# The flaky quarantine: tests that passed only on their classifying rerun. A quarantined test
# runs but does not gate. Limits (config `Flaky quarantine:` defaults): 8 tests, 7 days, 48 h to
# acknowledge, 100 consecutive passes to re-admit. Every verb works on the state file alone.
#
#   flaky.sh --state <file> [--now <epoch s>] record <id>      QUARANTINED <id>
#   flaky.sh --state <file> [--now <epoch s>] ack <id>
#   flaky.sh --state <file> [--now <epoch s>] pass <id> [<n>]  n passes in a row (default 1);
#                                                              READMITTED <id> at 100
#   flaky.sh --state <file> [--now <epoch s>] fail <id>        resets the pass count
#   flaky.sh --state <file> [--now <epoch s>] gate <results>   exit 1 when a failure or error
#                                                              is of a test that is not quarantined
#   flaky.sh --state <file> [--now <epoch s>] check            one `SUITE-OWNER TASK <kind> <id>`
#                                                              per entry over the cap (the ninth on:
#                                                              quarantine-full), older than 7 days
#                                                              (quarantine-expired) or not
#                                                              acknowledged in 48 h
#                                                              (quarantine-unacknowledged)
#
# <results> is what the adapter's `results` verb prints (`pass|failure|error|skipped <id> [<msg>]`).
# State: one entry per line, `<id> TAB <recorded epoch> TAB <acknowledged epoch or 0> TAB <passes>`,
# oldest first. Exit 0 (gate: nothing blocks), 1 (gate: a break), 64 usage.

set -uo pipefail

CAP="${PAD_FLAKY_CAP:-8}"
DAYS="${PAD_FLAKY_DAYS:-7}"
ACK_H="${PAD_FLAKY_ACK_HOURS:-48}"
PASSES="${PAD_FLAKY_PASSES:-100}"

state=""; now=""
while [ $# -gt 0 ]; do
  case "$1" in
    --state) state="${2:-}"; shift 2 ;;
    --now) now="${2:-}"; shift 2 ;;
    *) break ;;
  esac
done
verb="${1:-}"
[ -n "$state" ] && [ -n "$verb" ] || { echo "usage: flaky.sh --state <file> [--now <epoch>] record|ack|pass|fail|gate|check ..." >&2; exit 64; }
shift
[ -n "$now" ] || now="$(date +%s)"
[ -f "$state" ] || : >"$state"
tab=$'\t'

# in_state <id>: the entry's line, if any.
in_state() { awk -F'\t' -v id="$1" '$1 == id { print; found = 1 } END { exit !found }' "$state"; }
# rewrite <id> <recorded> <acked> <passes>: replace the entry (or drop it when recorded is empty).
rewrite() {
  awk -F'\t' -v OFS='\t' -v id="$1" -v r="$2" -v a="$3" -v p="$4" '
    $1 == id { if (r != "") print id, r, a, p; next } { print }' "$state" >"$state.new" && mv "$state.new" "$state"
}

case "$verb" in
  record)
    id="${1:?usage: record <id>}"
    in_state "$id" >/dev/null || printf '%s\t%s\t0\t0\n' "$id" "$now" >>"$state"
    echo "QUARANTINED $id"
    ;;
  ack)
    id="${1:?usage: ack <id>}"
    line="$(in_state "$id")" || exit 0
    IFS="$tab" read -r _ rec _ p <<<"$line"
    rewrite "$id" "$rec" "$now" "$p"
    ;;
  pass)
    id="${1:?usage: pass <id> [<n>]}"; n="${2:-1}"
    line="$(in_state "$id")" || exit 0
    IFS="$tab" read -r _ rec ack p <<<"$line"
    p=$((p + n))
    if [ "$p" -ge "$PASSES" ]; then
      rewrite "$id" "" "" ""
      echo "READMITTED $id"
    else
      rewrite "$id" "$rec" "$ack" "$p"
    fi
    ;;
  fail)
    id="${1:?usage: fail <id>}"
    line="$(in_state "$id")" || exit 0
    IFS="$tab" read -r _ rec ack _ <<<"$line"
    rewrite "$id" "$rec" "$ack" 0
    ;;
  gate)
    res="${1:?usage: gate <results>}"
    [ -f "$res" ] || { echo "flaky: no results file $res" >&2; exit 64; }
    rc=0
    while IFS= read -r l; do
      l="${l%$'\r'}"
      case "$l" in failure\ * | error\ *) ;; *) continue ;; esac
      rest="${l#* }"
      quarantined=0
      while IFS="$tab" read -r id _; do
        [ -n "$id" ] || continue
        case "$rest" in "$id" | "$id "*) quarantined=1; break ;; esac
      done <"$state"
      if [ "$quarantined" = 0 ]; then
        echo "GATE BREAK $rest"
        rc=1
      fi
    done <"$res"
    exit "$rc"
    ;;
  check)
    i=0
    while IFS="$tab" read -r id rec ack _; do
      [ -n "$id" ] || continue
      i=$((i + 1))
      [ "$i" -le "$CAP" ] || echo "SUITE-OWNER TASK quarantine-full $id"
      [ $((now - rec)) -le $((DAYS * 86400)) ] || echo "SUITE-OWNER TASK quarantine-expired $id"
      if [ "$ack" = 0 ] && [ $((now - rec)) -gt $((ACK_H * 3600)) ]; then
        echo "SUITE-OWNER TASK quarantine-unacknowledged $id"
      fi
    done <"$state"
    ;;
  *) echo "flaky: unknown verb $verb" >&2; exit 64 ;;
esac
