#!/usr/bin/env bash
# The acceptance half of the submit check. task-submit.sh calls the verbs; a suite ticket's
# report is checked with `verdicts`. No verb runs a test runner: each decides from files and git.
#
#   submit-acceptance.sh files [--suite] --adapter <runner.sh> --test-paths "<paths>" <KEY> <epic> <head>
#   submit-acceptance.sh grade --outcomes <file> --red-results <file> --head-results <file>
#   submit-acceptance.sh verdicts <report file> <id>...
#   submit-acceptance.sh submit [--test-paths "<paths>"] --ticket <file> <epic> <red> <head>
#
# files: every file added or changed between <epic> and <head> under the test paths must match
#   the adapter's `acceptance-pattern <KEY>` globs (matched on the file's name), unless --suite
#   (a suite ticket may change any test file). Fails `tests-in-acceptance: <path>`.
# grade: <outcomes> holds the test-designer's OUTCOMES lines `- <O>: <id>[, <id>] | expects: <text>`;
#   <red-results> and <head-results> hold what the adapter's `results` verb printed
#   (`pass|failure|error|skipped <id> [<message>]`) at the red commit and at the ticket head.
#   Grades follow suite-design.md §8: `red-grade 0: <id>` when the test passes at red (it tests
#   nothing new); `red-grade 1: <id>` when at red it is an `error`, did not run, or fails
#   without the text (an imprecise reason), or when it does not `pass` at the head; grade 2
#   (a `failure` with the text at red, then `pass`) is `SUBMIT OK`.
# verdicts: each <id> has exactly one line
#   `VERDICT <KEY> <id> promote|rewrite|retire <tier> — <why>` and <why> cites a section of
#   suite-design.md (`§<n>`).
#
# files and grade end on `SUBMIT OK` or `SUBMIT FAIL <rule>: <detail>` (exit 0 or 1); verdicts on
# `VERDICT OK` or `VERDICT FAIL <why>` (exit 0 or 1). Exit 64: usage.

set -uo pipefail

usage() {
  echo "usage: submit-acceptance.sh files|grade|verdicts ... (see the header)" >&2
  exit 64
}
sfail() { echo "SUBMIT FAIL $1: $2"; exit 1; }
vfail() { echo "VERDICT FAIL $1"; exit 1; }

verb="${1:-}"; [ -n "$verb" ] || usage
shift

case "$verb" in
  files)
    suite=0; adapter=""; paths="tests/"; pos=()
    while [ $# -gt 0 ]; do
      case "$1" in
        --suite) suite=1; shift ;;
        --adapter) adapter="${2:-}"; shift 2 ;;
        --test-paths) paths="${2:-}"; shift 2 ;;
        *) pos+=("$1"); shift ;;
      esac
    done
    [ "${#pos[@]}" -eq 3 ] && [ -n "$adapter" ] && [ -f "$adapter" ] || usage
    key="${pos[0]}"; epic="${pos[1]}"; head="${pos[2]}"
    if [ "$suite" = 1 ]; then echo "SUBMIT OK"; exit 0; fi
    globs="$(bash "$adapter" acceptance-pattern "$key")" || sfail tests-in-acceptance "adapter has no pattern for $key"
    # shellcheck disable=SC2086
    changed="$(git diff --name-only --no-renames --diff-filter=AM "$epic" "$head" -- $paths)"
    while IFS= read -r f; do
      [ -n "$f" ] || continue
      name="${f##*/}"
      ok=0
      while IFS= read -r g; do
        [ -n "$g" ] || continue
        g="${g#\*\*/}"
        # shellcheck disable=SC2053
        if [[ $name == $g ]]; then ok=1; break; fi
      done <<<"$globs"
      [ "$ok" = 1 ] || sfail tests-in-acceptance "$f"
    done <<<"$changed"
    echo "SUBMIT OK"
    ;;

  grade)
    outcomes=""; red=""; headres=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --outcomes) outcomes="${2:-}"; shift 2 ;;
        --red-results) red="${2:-}"; shift 2 ;;
        --head-results) headres="${2:-}"; shift 2 ;;
        *) usage ;;
      esac
    done
    [ -f "$outcomes" ] && [ -f "$red" ] && [ -f "$headres" ] || usage
    # files written on Windows carry CRLF
    tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
    tr -d '\r' <"$outcomes" >"$tmp/o"; tr -d '\r' <"$red" >"$tmp/r"; tr -d '\r' <"$headres" >"$tmp/h"
    outcomes="$tmp/o"; red="$tmp/r"; headres="$tmp/h"
    while IFS= read -r line; do
      case "$line" in *"| expects:"*) ;; *) continue ;; esac
      ids="${line%%| expects:*}"
      text="${line#*| expects:}"
      text="${text# }"; text="${text%"${text##*[![:space:]]}"}"
      ids="${ids#*: }"; ids="${ids%"${ids##*[![:space:]]}"}"
      while IFS= read -r id; do
        id="${id# }"
        [ -n "$id" ] || continue
        got=""
        while IFS= read -r r; do
          case "$r" in
            "pass $id" | "pass $id "*) sfail "red-grade 0" "$id" ;;
            "failure $id" | "failure $id "*) got="$r"; break ;;
          esac
        done <"$red"
        # grade 1: an error, no run, or a failure that does not say the stated text
        [ -n "$got" ] || sfail "red-grade 1" "$id"
        msg="${got#failure "$id"}"
        case "$msg" in *"$text"*) ;; *) sfail "red-grade 1" "$id" ;; esac
        okhead=0
        while IFS= read -r r; do
          case "$r" in "pass $id" | "pass $id "*) okhead=1; break ;; esac
        done <"$headres"
        [ "$okhead" = 1 ] || sfail "red-grade 1" "$id"
      done <<<"$(printf '%s\n' "$ids" | sed 's/, */\n/g')"
    done <"$outcomes"
    echo "SUBMIT OK"
    ;;

  submit)
    # What task-submit.sh calls: resolve the adapter and the ticket's key, then `files`, and
    # `grade` when PAD_RED_RESULTS and PAD_HEAD_RESULTS name the adapter's results at the red
    # commit and at the head. No `Runner:` under the config's `## Test regime`, or no ticket:
    # nothing to check.
    paths="tests/"; ticket=""; pos=()
    while [ $# -gt 0 ]; do
      case "$1" in
        --test-paths) paths="${2:-}"; shift 2 ;;
        --ticket) ticket="${2:-}"; shift 2 ;;
        *) pos+=("$1"); shift ;;
      esac
    done
    [ "${#pos[@]}" -eq 3 ] || usage
    epic="${pos[0]}"; red="${pos[1]}"; head="${pos[2]}"
    [ -n "$ticket" ] || { echo "SUBMIT OK"; exit 0; }
    here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    top="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
    cfg="$top/.claude/workflow/config.md"
    runner=""
    if [ -f "$cfg" ]; then
      runner="$(bash "$here/regime.sh" get Runner --config "$cfg")"
    fi
    [ -n "$runner" ] || { echo "SUBMIT OK"; exit 0; }
    adapter="$top/.claude/pad-plugins/runners/$runner.sh"
    [ -f "$adapter" ] || adapter="$here/../runners/$runner.sh"
    [ -f "$adapter" ] || sfail tests-in-acceptance "no adapter for runner $runner"
    key="$(basename "$ticket" .md)"
    flag=()
    case "$key" in *-suite-*) flag=(--suite) ;; esac
    out="$(bash "$here/submit-acceptance.sh" files ${flag[@]+"${flag[@]}"} --adapter "$adapter" --test-paths "$paths" "$key" "$epic" "$head")" ||
      { echo "$out" | tail -n 1; exit 1; }
    # The grade: the red commit's message carries the test-designer's OUTCOMES lines.
    outc="$(mktemp)"
    git log -1 --format=%B "$red" | tr -d '\r' | grep -F '| expects:' >"$outc" || true
    if [ -s "$outc" ]; then
      redres="${PAD_RED_RESULTS:-}"; headres="${PAD_HEAD_RESULTS:-}"
      if [ -z "$redres" ] || [ -z "$headres" ]; then
        # No override: run the acceptance ids at the red commit and at the head, each in a
        # throwaway worktree, through pad-test.sh, and keep the adapter's results lines.
        ids=()
        while IFS= read -r l; do
          l="${l%%| expects:*}"; l="${l#*: }"
          while IFS= read -r i; do
            i="${i# }"; i="${i%"${i##*[![:space:]]}"}"
            [ -n "$i" ] && ids+=("$i")
          done <<<"$(printf '%s\n' "$l" | sed 's/, */\n/g')"
        done <"$outc"
        main="$(cd "$top" && cd "$(git rev-parse --git-common-dir)/.." && pwd)"
        gid="grade-$$"
        work="$(mktemp -d)"
        trap 'rm -rf "$work"' EXIT
        # results_at <commit> <out file>
        results_at() {
          local wt="$work/wt-${1:0:8}" r
          git worktree add --detach --quiet "$wt" "$1" >/dev/null 2>&1 || { : >"$2"; return 0; }
          (cd "$wt" && bash "$here/pad-test.sh" --run "$gid" --ticket "$key" --role gate --ids "${ids[@]}" >/dev/null 2>&1)
          r="$(ls -t "$main"/.work/runs/"$gid"/pad-state/report/*/results.lines 2>/dev/null | head -n 1)"
          if [ -n "$r" ]; then tr -d '\r' <"$r" >"$2"; else : >"$2"; fi
          rm -rf "$main/.work/runs/$gid/pad-state/report"
          git worktree remove --force "$wt" >/dev/null 2>&1 || true
        }
        results_at "$red" "$work/red.txt"
        results_at "$head" "$work/head.txt"
        rm -rf "$main/.work/runs/$gid"
        redres="$work/red.txt"; headres="$work/head.txt"
      fi
      out="$(bash "$here/submit-acceptance.sh" grade --outcomes "$outc" --red-results "$redres" --head-results "$headres")" ||
        { rm -f "$outc"; echo "$out" | tail -n 1; exit 1; }
    fi
    rm -f "$outc"
    echo "SUBMIT OK"
    ;;

  verdicts)
    report="${1:-}"; [ -f "$report" ] || usage
    shift
    [ $# -gt 0 ] || usage
    tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
    tr -d '\r' <"$report" >"$tmp/rep"; report="$tmp/rep"
    # every VERDICT line must be well formed, whichever test it names
    while IFS= read -r l; do
      [[ $l =~ ^VERDICT\ [^\ ]+\ .+\ (promote|rewrite|retire)\ [^\ ]+\ —\ .*§[0-9]+ ]] ||
        vfail "malformed line (want: VERDICT <KEY> <id> promote|rewrite|retire <tier> — §<n> <why>): $l"
    done <<<"$(grep -E '^VERDICT ' "$report" || true)"
    for id in "$@"; do
      n="$(grep -cE "^VERDICT [^ ]+ $(printf '%s' "$id" | sed 's/[][\.*^$/]/\\&/g') (promote|rewrite|retire) " "$report" || true)"
      [ "$n" = 1 ] || vfail "$n lines for $id (want exactly one)"
    done
    echo "VERDICT OK"
    ;;

  *) usage ;;
esac
