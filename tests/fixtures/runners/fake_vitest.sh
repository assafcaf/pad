#!/usr/bin/env bash
# A vitest double: `fake_vitest.sh run --reporter=json --outputFile=<path> ...` writes the JSON
# in $FAKE_VITEST_JSON to <path> and exits $FAKE_VITEST_EXIT (default 1). It logs its argv to
# $FAKE_LOG.
echo "vitest $*" >> "${FAKE_LOG:-/dev/null}"
out=""
for a in "$@"; do case "$a" in --outputFile=*) out="${a#--outputFile=}" ;; esac; done
[ -n "$out" ] && cat "${FAKE_VITEST_JSON:?}" > "$out"
exit "${FAKE_VITEST_EXIT:-1}"
