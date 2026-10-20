#!/usr/bin/env bash
# Runner adapter: pytest. `pad-test.sh` is its only caller (the verbs below, nothing else).
#
#   pytest.sh run <report-dir> (--tier-arg <arg> | --ids <id>...) [--workers n] [--kill-per-test s] [--shuffle]
#   pytest.sh results <report-dir>      lines `pass|failure|error|skipped <id> [<message>]`
#   pytest.sh runner-names              command prefixes to deny (the agents go through pad-test.sh)
#   pytest.sh protected-files           globs of the runner's own configuration
#   pytest.sh acceptance-pattern <KEY>  the file glob of a ticket's acceptance tests
#   pytest.sh capabilities              contract-fast leak-check shuffle
#
# Ids are `<file>::<test>`; a whole file is not an id (exit 64 with the form). It runs in the
# project's directory and needs python (`python` or `python3` on the PATH) with pytest. The report
# is written by the runner plugin next to this file (pad_runner_plugin.py): it records every test's
# outcome, enforces the fast-tier contract when PAD_TIER=fast (a test that opens a socket or starts
# a subprocess fails at the call), records the processes the tests started, and fails the run with
# `LEAK <pid> <command>` for one still alive at the end.
# --workers needs pytest-xdist and --kill-per-test pytest-timeout; without them they are ignored.

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
verb="${1:-}"
[ $# -gt 0 ] && shift

py() {
  local c
  for c in python python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys' >/dev/null 2>&1; then echo "$c"; return 0; fi
  done
  return 1
}

case "$verb" in
  runner-names) printf '%s\n' pytest py.test "python -m pytest" "python3 -m pytest"; exit 0 ;;
  protected-files) printf '%s\n' conftest.py pytest.ini tox.ini setup.cfg pyproject.toml; exit 0 ;;
  acceptance-pattern)
    key="${1:?usage: pytest.sh acceptance-pattern <KEY>}"
    # one glob per line: the key as an identifier (test_store_KAN_12.py), and as written
    echo "**/test_*$(printf '%s' "$key" | tr '-' '_')*.py"
    echo "**/test_*$key*.py"
    exit 0 ;;
  capabilities) echo "contract-fast leak-check shuffle"; exit 0 ;;
  results)
    rd="${1:?usage: pytest.sh results <report-dir>}"
    [ -f "$rd/results" ] && awk '!seen[$0]++' "$rd/results"
    exit 0 ;;
  run) ;;
  *) echo "pytest.sh: unknown verb '$verb'" >&2; exit 64 ;;
esac

# --- run -------------------------------------------------------------------------------------

rd="${1:?usage: pytest.sh run <report-dir> ...}"
shift
selector=(); ids=(); workers=""; kill=""; shuffle=0
while [ $# -gt 0 ]; do
  case "$1" in
    --tier-arg) read -ra selector <<<"${2:-}"; shift 2 ;;
    --ids)
      shift
      while [ $# -gt 0 ]; do case "$1" in --*) break ;; esac; ids+=("$1"); shift; done ;;
    --workers) workers="${2:-}"; shift 2 ;;
    --kill-per-test) kill="${2:-}"; shift 2 ;;
    --shuffle) shuffle=1; shift ;;
    *) echo "pytest.sh: unknown option '$1'" >&2; exit 64 ;;
  esac
done

for id in ${ids[@]+"${ids[@]}"}; do
  case "$id" in
    *::*) ;;
    *) echo "pytest ids look like <file>::<test>; '$id' is a whole file" >&2; exit 64 ;;
  esac
done

python="$(py)" || { echo "pytest.sh: no python on the PATH" >&2; exit 2; }
mkdir -p "$rd" || exit 2
rm -f "$rd/results" "$rd/leaks"

plugdir="$here"
if command -v cygpath >/dev/null 2>&1; then plugdir="$(cygpath -m "$here")"; fi
rdp="$rd"
if command -v cygpath >/dev/null 2>&1; then rdp="$(cygpath -m "$rd")"; fi

args=(-p pad_runner_plugin -p no:cacheprovider --rootdir . -q)
if [ -n "$workers" ] && [ "$workers" -gt 1 ] 2>/dev/null && "$python" -c 'import xdist' >/dev/null 2>&1; then
  args+=(-n "$workers")
fi
if [ -n "$kill" ] && "$python" -c 'import pytest_timeout' >/dev/null 2>&1; then
  args+=("--timeout=$kill")
fi

targets=()
if [ "${#ids[@]}" -gt 0 ]; then
  targets=("${ids[@]}")
else
  shopt -s globstar nullglob
  for w in ${selector[@]+"${selector[@]}"}; do
    case "$w" in
      *[*?[]*) matches=($w); [ "${#matches[@]}" -gt 0 ] && targets+=("${matches[@]}") ;;
      *) targets+=("$w") ;;
    esac
  done
  shopt -u globstar nullglob
  if [ "${#targets[@]}" -eq 0 ]; then echo "pytest.sh: the selection matched no files" >&2; exit 5; fi
fi

sep=":"; command -v cygpath >/dev/null 2>&1 && sep=";"
PAD_REPORT_DIR="$rdp" PAD_SHUFFLE="$shuffle" PYTHONPATH="$plugdir${PYTHONPATH:+$sep$PYTHONPATH}" \
  "$python" -m pytest "${args[@]}" "${targets[@]}"
code=$?

if [ -s "$rd/leaks" ]; then
  while IFS= read -r line; do echo "LEAK $line"; done < "$rd/leaks"
  [ "$code" -ne 0 ] || code=1
fi
exit "$code"
