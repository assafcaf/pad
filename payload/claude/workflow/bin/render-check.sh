#!/usr/bin/env bash
# Render one state of a surface to a file through the surface's configured Render command.
#
#   render-check.sh --surface <name> --route <r> --viewport WxH [--state <file>] --out <png>
#
# The command is the `Render command` cell of the surface's row in the `## Surfaces` table of
# .claude/workflow/config.md (this worktree's, else the main checkout's). Columns are found by
# header name; surrounding backticks are stripped, so a command cannot contain `|`. The cell is a
# template: {route}, {viewport} (WxH), {width}, {height}, {state} (empty without --state) and
# {out} (absolute) are replaced literally, unquoted; quote them in the template if they may hold
# blanks. It runs under bash at the top of the current worktree; its output goes to stderr. Any
# file already at --out is removed first, and --out's directory is created.
#
# PAD assumes no web app: the command may drive a browser, a terminal capture, a native
# screenshot tool or anything else that writes the file.
#
# Last line: `RENDER OK <out>` (exit 0: the command exited 0 and --out exists and is non-empty),
# `RENDER FAIL <surface>: <why>` (exit 1), `RENDER NONE <surface>` (exit 1: no Render command is
# configured for the surface). Exit 64: usage.

set -uo pipefail

usage() {
  echo "usage: render-check.sh --surface <name> --route <r> --viewport WxH [--state <file>] --out <png>" >&2
  exit 64
}

surface="" route="" viewport="" state="" out=""
seen=" "
while [ $# -gt 0 ]; do
  [ $# -ge 2 ] || usage
  case "$1" in
    --surface) surface="$2" ;;
    --route) route="$2" ;;
    --viewport) viewport="$2" ;;
    --state) state="$2" ;;
    --out) out="$2" ;;
    *) usage ;;
  esac
  seen="$seen$1 "
  shift 2
done
for f in surface route viewport out; do
  case "$seen" in *" --$f "*) ;; *) usage ;; esac
done
[ -n "$surface" ] && [ -n "$out" ] || usage
case "$viewport" in
  *x*) width="${viewport%%x*}"; height="${viewport#*x}" ;;
  *) usage ;;
esac
case "$width$height" in ''|*[!0-9]*) usage ;; esac
[ -n "$width" ] && [ -n "$height" ] || usage

fail() { echo "RENDER FAIL $surface: $1"; exit 1; }

# --out is resolved against the caller's directory before the command moves to the worktree top.
case "$out" in
  /*|[A-Za-z]:[/\\]*) abs_out="$out" ;;
  *) abs_out="$(pwd)/$out" ;;
esac

top="$(git rev-parse --show-toplevel 2>/dev/null)" || top="$(pwd)"
cfg="$top/.claude/workflow/config.md"
if [ ! -f "$cfg" ]; then
  common="$(git rev-parse --git-common-dir 2>/dev/null)" &&
    main="$(cd "$top" && cd "$common/.." && pwd)" && cfg="$main/.claude/workflow/config.md"
fi
[ -f "$cfg" ] || fail "no config at .claude/workflow/config.md"

# The surface's row as `found<US>command`; `found` is 1 when the row exists.
row="$(awk -F'|' -v want="$surface" '
  function clean(s) { gsub(/^[ \t]+|[ \t]+$/, "", s); if (s ~ /^`.*`$/) s = substr(s, 2, length(s) - 2); return s }
  { sub(/\r$/, "") }
  /^## / { insec = ($0 ~ /^## Surfaces[ \t]*$/); hdr = 0; next }
  insec && /^\|/ {
    if (!hdr) { for (i = 2; i < NF; i++) col[clean($i)] = i; hdr = 1; next }
    if ($0 ~ /^\|[ \t]*:?-/) next
    if (!("Surface" in col) || clean($(col["Surface"])) != want) next
    cmd = ("Render command" in col) ? clean($(col["Render command"])) : ""
    printf "1\037%s\n", cmd; exit
  }' "$cfg")"

[ -n "$row" ] || fail "no row for surface '$surface' in the Surfaces table of $cfg"
template="${row#*$'\037'}"
case "$template" in ''|-|'<'*'>') echo "RENDER NONE $surface"; exit 1 ;; esac

# bash 5.2 would read & in a replacement as the matched text; values must land literally.
shopt -u patsub_replacement 2>/dev/null
cmd="$template"
cmd="${cmd//\{route\}/$route}"
cmd="${cmd//\{viewport\}/$viewport}"
cmd="${cmd//\{width\}/$width}"
cmd="${cmd//\{height\}/$height}"
cmd="${cmd//\{state\}/$state}"
cmd="${cmd//\{out\}/$abs_out}"

mkdir -p "$(dirname "$abs_out")" || fail "cannot create the directory of $out"
rm -f "$abs_out" || fail "cannot remove the old $out"

(cd "$top" && bash -c "$cmd") >&2
code=$?
[ "$code" -eq 0 ] || fail "render command exited $code"
[ -f "$abs_out" ] || fail "render command wrote no file at $out"
[ -s "$abs_out" ] || fail "render command wrote an empty file at $out"
echo "RENDER OK $out"
