#!/usr/bin/env bash
# Runner adapter: vitest. `pad-test.sh` is its only caller (the verbs below, nothing else).
#
#   vitest.sh run <report-dir> (--tier-arg <arg> | --ids <id>...) [--workers n] [--kill-per-test s] [--shuffle]
#   vitest.sh results <report-dir>      lines `pass|failure|error|skipped <id> [<message>]`
#   vitest.sh runner-names | protected-files | acceptance-pattern <KEY> | capabilities
#
# Ids are `<file> > <suite> > <test>`, the file relative to the project. `run` starts
# `${PAD_VITEST:-npx vitest} run --reporter=json --outputFile=<report-dir>/vitest.json ...` in the
# project's directory; `results` reads that JSON with awk (no node needed to read it). A test file
# that failed to load is one `error <file> <message>` line.
#
# runners/vitest-pad-preload.mjs is preloaded into the workers (NODE_OPTIONS=--import): with
# PAD_TIER=fast a test that opens a socket or starts a subprocess fails at the call, and every
# process a test starts is recorded, so one still alive when the run ends fails it as
# `LEAK <pid> <command>` (checked with node, which a vitest project has).

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
verb="${1:-}"
[ $# -gt 0 ] && shift

case "$verb" in
  runner-names) printf '%s\n' vitest "npx vitest" "pnpm vitest" "yarn vitest" "npm test"; exit 0 ;;
  protected-files) printf '%s\n' 'vitest.config.*' 'vite.config.*' 'vitest.workspace.*' 'vitest.setup.*'; exit 0 ;;
  acceptance-pattern)
    key="${1:?usage: vitest.sh acceptance-pattern <KEY>}"
    echo "**/*.$key.test.*"
    exit 0 ;;
  capabilities) echo "contract-fast leak-check shuffle"; exit 0 ;;
  results)
    rd="${1:?usage: vitest.sh results <report-dir>}"
    json="$rd/vitest.json"
    [ -f "$json" ] || exit 0
    cwd1="$(pwd)"; cwd2="$(pwd -W 2>/dev/null || pwd)"
    tr -d '\r' < "$json" | awk -v c1="$cwd1" -v c2="$cwd2" '
      function unq(t) {
        t = substr(t, 2, length(t) - 2)
        gsub(/\\n|\\t|\\r/, " ", t); gsub(/\\"/, "\"", t); gsub(/\\\//, "/", t); gsub(/\\\\/, "\\", t)
        return t
      }
      function rel(n,   p) {
        gsub(/\\/, "/", n)
        p = c1; gsub(/\\/, "/", p); if (index(n, p "/") == 1) return substr(n, length(p) + 2)
        p = c2; gsub(/\\/, "/", p); if (index(n, p "/") == 1) return substr(n, length(p) + 2)
        return n
      }
      function one(m) { gsub(/[ \t]+/, " ", m); sub(/^ /, "", m); return substr(m, 1, 300) }
      function leaf(v,   n, i, j, k) {
        n = split(path, p, ".")
        if (p[1] != "testResults" || n < 3) return
        i = p[2] + 0
        if (i + 1 > nfiles) nfiles = i + 1
        if (n == 3 && p[3] == "name") fname[i] = rel(v)
        else if (n == 3 && p[3] == "status") fstatus[i] = v
        else if (n == 3 && p[3] == "message") fmsg[i] = v
        else if (p[3] == "assertionResults" && n >= 5) {
          j = p[4] + 0
          if (j + 1 > nassert[i]) nassert[i] = j + 1
          if (n == 5 && p[5] == "title") title[i, j] = v
          else if (n == 5 && p[5] == "status") astatus[i, j] = v
          else if (n == 6 && p[5] == "ancestorTitles") { k = p[6] + 0; anc[i, j, k] = v; if (k + 1 > nanc[i, j]) nanc[i, j] = k + 1 }
          else if (n == 6 && p[5] == "failureMessages" && p[6] == "0") amsg[i, j] = v
        }
      }
      { s = s $0 " " }
      END {
        n = length(s); pos = 1; d = 0
        while (pos <= n) {
          len = 8192
          ok = 0
          while (1) {
            chunk = substr(s, pos, len)
            if (match(chunk, /^[ \t]*("([^"\\]|\\.)*"|[]\[{},:]|[^]\[{},:" \t]+)/) && (RLENGTH < length(chunk) || pos + len > n)) { ok = 1; break }
            if (pos + len > n) break
            len *= 2
          }
          if (!ok) break
          t = substr(chunk, 1, RLENGTH); pos += RLENGTH
          sub(/^[ \t]+/, "", t)
          c = substr(t, 1, 1)
          if (c == "{" || c == "[") {
            d++; typ[d] = (c == "{") ? "o" : "a"; cur[d] = (c == "{") ? "" : 0; expect[d] = (c == "{")
          } else if (c == "}" || c == "]") {
            d--
          } else if (c == ",") {
            if (typ[d] == "a") cur[d]++; else expect[d] = 1
          } else if (c == ":") {
            expect[d] = 0
          } else if (typ[d] == "o" && expect[d]) {
            cur[d] = unq(t)
          } else {
            path = ""
            for (q = 1; q <= d; q++) path = path (q > 1 ? "." : "") cur[q]
            leaf((c == "\"") ? unq(t) : t)
          }
        }
        for (i = 0; i < nfiles; i++) {
          if (nassert[i] == 0) {
            if (fstatus[i] == "failed") print "error " fname[i] " " one(fmsg[i] != "" ? fmsg[i] : "the test file failed")
            continue
          }
          for (j = 0; j < nassert[i]; j++) {
            id = fname[i]
            for (k = 0; k < nanc[i, j]; k++) id = id " > " anc[i, j, k]
            id = id " > " title[i, j]
            st = astatus[i, j]
            if (st == "passed") print "pass " id
            else if (st == "failed") print "failure " id " " one(amsg[i, j])
            else print "skipped " id
          }
        }
      }'
    exit 0 ;;
  run) ;;
  *) echo "vitest.sh: unknown verb '$verb'" >&2; exit 64 ;;
esac

# --- run -------------------------------------------------------------------------------------

rd="${1:?usage: vitest.sh run <report-dir> ...}"
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
    *) echo "vitest.sh: unknown option '$1'" >&2; exit 64 ;;
  esac
done

for id in ${ids[@]+"${ids[@]}"}; do
  case "$id" in
    *" > "*) ;;
    *) echo "vitest ids look like '<file> > <suite> > <test>'; '$id' is a whole file" >&2; exit 64 ;;
  esac
done

mkdir -p "$rd" || exit 2
rm -f "$rd/vitest.json" "$rd/spawned"

# The selection: files, and for ids a -t regex of the test names.
targets=(); names=""
if [ "${#ids[@]}" -gt 0 ]; then
  for id in "${ids[@]}"; do
    f="${id%% > *}"
    rest="${id#* > }"
    case " ${targets[*]-} " in *" $f "*) ;; *) targets+=("$f") ;; esac
    full="$(printf '%s' "${rest//' > '/ }" | sed -e 's/[][\\.*+?^${}()|/]/\\&/g')"
    names="${names:+$names|}$full"
  done
else
  targets=(${selector[@]+"${selector[@]}"})
fi

args=(--reporter=json "--outputFile=$rd/vitest.json")
[ "${#targets[@]}" -eq 0 ] || args+=("${targets[@]}")
[ -z "$names" ] || args+=(-t "($names)")
[ -z "$workers" ] || args+=("--maxWorkers=$workers")
[ -z "$kill" ] || args+=("--testTimeout=$((kill * 1000))")
[ "$shuffle" -eq 0 ] || args+=(--sequence.shuffle)

runner="${PAD_VITEST:-npx vitest}"
eval "cmd=($runner)"

preload="$here/vitest-pad-preload.mjs"
rdp="$rd"
if command -v cygpath >/dev/null 2>&1; then preload="$(cygpath -m "$preload")"; rdp="$(cygpath -m "$rd")"; fi

NODE_OPTIONS="${NODE_OPTIONS:+$NODE_OPTIONS }--import file:///${preload#/}" PAD_REPORT_DIR="$rdp" \
  "${cmd[@]}" run "${args[@]}"
code=$?

# Leaks: processes the tests started that are still alive.
if [ -s "$rd/spawned" ] && command -v node >/dev/null 2>&1; then
  leaks="$(node -e '
    const fs = require("fs");
    for (const line of fs.readFileSync(process.argv[1], "utf8").split(/\r?\n/)) {
      const m = /^(\d+) (.*)$/.exec(line); if (!m) continue;
      try { process.kill(+m[1], 0); console.log(`LEAK ${m[1]} ${m[2]}`); try { process.kill(+m[1], "SIGKILL"); } catch {} } catch {}
    }' "$rd/spawned")"
  if [ -n "$leaks" ]; then
    printf '%s\n' "$leaks"
    [ "$code" -ne 0 ] || code=1
  fi
fi
exit "$code"
