#!/usr/bin/env bash
# Runner adapter TEMPLATE. Copy to .claude/pad-plugins/runners/<name>.sh (`/setup-workflow` does
# this for a runner PAD does not ship) and fill in the marked parts. `pad-test.sh` calls the verbs
# below and nothing else; no other PAD script names a runner.
#
# The adapter is accepted only after its self-test passes, against four fixture tests you provide:
#   one that fails as an assertion      -> results: `failure <id> <message>`
#   one that passes                     -> results: `pass <id>`
#   one whose import cannot load        -> results: `error <id-or-file> <message>`  (not `failure`)
#   and `results` returns the failing test's id.
#
# Verbs
#   run <report-dir> (--tier-arg <arg> | --ids <id>...) [--workers n] [--kill-per-test s] [--shuffle]
#       Run the selection, leave whatever `results` needs in <report-dir>. Exit non-zero when a test
#       failed or the run did not complete. A whole file is not an id: exit 64 and print the id form.
#   results <report-dir>
#       Lines `pass|failure|error|skipped <id> [<message>]`, one per test. An id has no spaces
#       before its message. Print nothing when the run left no report.
#   runner-names
#       The command prefixes the settings deny to agents (they run tests through pad-test.sh).
#   protected-files
#       Globs of the runner's own configuration; only a suite ticket may change them.
#   acceptance-pattern <KEY>
#       The file glob(s), one per line, of a ticket's acceptance tests (the key in the file name).
#   capabilities
#       Any of: contract-fast contract-heavy leak-check mutation shuffle (a declaration is a
#       promise: `contract-fast` fails a fast test that opens a socket or starts a subprocess at the
#       call; `leak-check` prints `LEAK <pid> <command>` and exits non-zero when a process the run
#       started is still alive at its end).
#   mutate <report-dir> <paths>...      only if `mutation` is declared
#       Lines `killed|survived <mutant id> <test id>`.
#
# PAD_TIER (fast|heavy|epic) is in the environment of `run`; PAD_REPORT_DIR is not set, use the
# <report-dir> argument.

verb="${1:-}"
[ $# -gt 0 ] && shift

case "$verb" in
  run)
    rd="${1:?report dir}"; shift
    mkdir -p "$rd"
    # FILL IN: start the runner with the selection and write its report into "$rd".
    echo "TEMPLATE.sh: fill in the run verb" >&2
    exit 2 ;;
  results)
    # FILL IN: read "${1}" and print `pass|failure|error|skipped <id> [<message>]` lines.
    exit 0 ;;
  runner-names) echo "your-runner" ;;
  protected-files) echo "your-runner.config" ;;
  acceptance-pattern) echo "**/*${1:?key}*" ;;
  capabilities) echo "" ;;
  *) echo "adapter: unknown verb '$verb'" >&2; exit 64 ;;
esac
