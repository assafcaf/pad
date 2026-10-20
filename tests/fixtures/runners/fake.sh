#!/usr/bin/env bash
# A runner adapter double for pad-test.sh's tests: it logs every call to $FAKE_LOG and plays back
# $FAKE_STATE/results.<n> (the n-th `run`) and $FAKE_STATE/exit.<n> (its exit code; else 1 when a
# failure or error line is in the results, else 0). A whole-file id is refused (exit 64) the way
# an adapter that wants `<file>::<test>` ids refuses it.
verb="${1:-}"
[ $# -gt 0 ] && shift
echo "$verb $*" >> "${FAKE_LOG:?}"
case "$verb" in
  run)
    rd="${1:-}"; shift
    if [ "${1:-}" = --ids ]; then
      shift
      for id in "$@"; do
        case "$id" in --*) break ;; esac
        case "$id" in
          *::*) ;;
          *) echo "ids look like <file>::<test>; '$id' is a whole file" >&2; exit 64 ;;
        esac
      done
    fi
    n=$(( $(cat "${FAKE_STATE:?}/count" 2>/dev/null || echo 0) + 1 ))
    echo "$n" > "$FAKE_STATE/count"
    mkdir -p "$rd"
    if [ -f "$FAKE_STATE/results.$n" ]; then cp "$FAKE_STATE/results.$n" "$rd/results"; else : > "$rd/results"; fi
    if [ -f "$FAKE_STATE/exit.$n" ]; then exit "$(tr -d '\r\n' < "$FAKE_STATE/exit.$n")"; fi
    grep -qE '^(failure|error) ' "$rd/results" && exit 1
    exit 0 ;;
  results) cat "${1:?}/results" ;;
  runner-names) echo fake ;;
  protected-files) echo 'conftest.fake' ;;
  acceptance-pattern) echo "tests/**/*${1:-}*" ;;
  capabilities) echo "${FAKE_CAPS-contract-fast leak-check shuffle}" ;;
  *) echo "fake adapter: unknown verb '$verb'" >&2; exit 64 ;;
esac
