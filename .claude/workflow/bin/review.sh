#!/usr/bin/env bash
# Write a run's wave review packet from its board.md and evidence, from any worktree.
#
#   review.sh --run <id> [--since <n>]
#
# Reads <main checkout>/.work/runs/<id>/: board.md (rows `| Key | Owner | Status | Branch | Sha |
# Evidence |`, columns found by header name), <KEY>.md evidence files (render-evidence.sh) and
# evidence/<KEY>/ render pairs (reference.png, app.png, optional verdict.md). Writes
# review-<n>.md and review-<n>.html there, n the next free number, holding:
#
#   - Merged: a table of the done rows not listed by packets 1..<since> (default: every earlier
#     packet), with key, sha and evidence path. Each packet records its keys in a
#     `<!-- review-keys: ... -->` line, which is what later packets read. --since 0 lists all.
#   - Render pairs: per listed key with an evidence/<KEY>/ directory, reference and app images
#     (paths relative to the packet) and verdict.md's text.
#   - Evidence: the `- ` lines of each listed key's evidence file.
#   - Unverified: listed done keys with no evidence file (the <KEY>.md, or the board's Evidence
#     path when that names a file) or an incomplete render pair, and every row not done.
#
# The HTML has the same content in one file with inline CSS and the two images side by side; the
# images are linked by relative path, not embedded. This script sends no notification; the
# orchestrator does.
#
# Last line: `REVIEW <path to md>` (exit 0; cygpath -m form where cygpath exists) | `REVIEW FAIL <run>: <why>` (exit 1). Exit 64: usage.

set -uo pipefail

usage() { echo "usage: review.sh --run <id> [--since <n>]" >&2; exit 64; }

run="" since=""
while [ $# -gt 0 ]; do
  [ $# -ge 2 ] || usage
  case "$1" in
    --run) run="$2" ;;
    --since) since="$2" ;;
    *) usage ;;
  esac
  shift 2
done
[ -n "$run" ] || usage
case "$since" in *[!0-9]*) usage ;; esac

fail() { echo "REVIEW FAIL $run: $1"; exit 1; }

top="$(git rev-parse --show-toplevel 2>/dev/null)" || fail "not a git repository"
main="$(cd "$top" && cd "$(git rev-parse --git-common-dir)/.." && pwd)" || fail "cannot find the main checkout"
dir="$main/.work/runs/$run"
board="$dir/board.md"
[ -f "$board" ] || fail "no board at $board"

# Next free packet number, and the default --since: every earlier packet.
n=1
while [ -e "$dir/review-$n.md" ]; do n=$((n + 1)); done
[ -n "$since" ] || since=$((n - 1))

prior=" "
k=1
while [ "$k" -le "$since" ]; do
  if [ -f "$dir/review-$k.md" ]; then
    keys="$(sed -n 's/^<!-- review-keys:\(.*\)-->.*/\1/p' "$dir/review-$k.md" | tr -d '\r')"
    for x in $keys; do prior="$prior$x "; done
  fi
  k=$((k + 1))
done

# Board rows as key TAB status TAB sha TAB evidence.
rows="$(awk -F'|' '
  function clean(s) { gsub(/^[ \t]+|[ \t]+$/, "", s); if (s ~ /^`.*`$/) s = substr(s, 2, length(s) - 2); return s }
  function cell(name) { return (name in col) ? clean($(col[name])) : "-" }
  { sub(/\r$/, "") }
  /^\|/ {
    if (!hdr) { for (i = 2; i < NF; i++) col[clean($i)] = i; hdr = 1; next }
    if ($0 ~ /^\|[ \t]*:?-/) next
    k = cell("Key"); if (k == "") next
    printf "%s\t%s\t%s\t%s\n", k, cell("Status"), cell("Sha"), cell("Evidence")
  }' "$board")"

# evidence_file <key> <board evidence>: the evidence file's path relative to $dir (or absolute),
# empty when there is none.
evidence_file() {
  local ev="$2"
  if [ -n "$ev" ] && [ "$ev" != "-" ]; then
    case "$ev" in
      /*|[A-Za-z]:[/\\]*) [ -f "$ev" ] && { printf '%s' "$ev"; return; } ;;
      *) [ -f "$dir/$ev" ] && { printf '%s' "$ev"; return; }
         [ -f "$main/$ev" ] && { printf '%s' "$main/$ev"; return; } ;;
    esac
  fi
  [ -f "$dir/$1.md" ] && printf '%s' "$1.md"
}

listed=()      # key TAB sha TAB evidence file
unverified=()  # one text line each
while IFS=$'\t' read -r key status sha ev; do
  [ -n "$key" ] || continue
  st="$(printf '%s' "$status" | tr '[:upper:]' '[:lower:]')"
  if [ "$st" != done ]; then
    unverified+=("$key: status $status, not merged")
    continue
  fi
  case "$prior" in *" $key "*) continue ;; esac
  file="$(evidence_file "$key" "$ev")"
  listed+=("$key"$'\t'"$sha"$'\t'"$file")
  [ -n "$file" ] || unverified+=("$key: done but no evidence file")
  pair="$dir/evidence/$key"
  if [ -d "$pair" ]; then
    for img in reference.png app.png; do
      [ -s "$pair/$img" ] || unverified+=("$key: render pair incomplete, no $img")
    done
  fi
done <<<"$rows"

keys_line=""
for l in "${listed[@]+"${listed[@]}"}"; do keys_line="$keys_line ${l%%$'\t'*}"; done

esc() { sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' -e 's/"/\&quot;/g'; }
evidence_lines() {  # <file>: the `- ` lines, CR stripped
  local f="$1"
  case "$f" in /*|[A-Za-z]:[/\\]*) ;; *) f="$dir/$f" ;; esac
  grep '^- ' "$f" 2>/dev/null | tr -d '\r'
}

md="$dir/review-$n.md"
html="$dir/review-$n.html"
title="Review $n: $run"

{
  printf '# %s\n\n' "$title"
  printf '> Written by review.sh from board.md and the evidence files on %s. It sends no\n' "$(date +%Y-%m-%d)"
  if [ "$since" -eq 0 ]; then printf '> notification; the orchestrator does. Lists every done row.\n\n'
  else printf '> notification; the orchestrator does. Leaves out rows listed by packets 1..%s.\n\n' "$since"; fi
  printf '<!-- review-keys:%s -->\n\n' "$keys_line"

  printf '## Merged\n\n'
  if [ "${#listed[@]}" -eq 0 ]; then
    printf 'No rows merged since the previous packet.\n\n'
  else
    printf '| Key | Sha | Evidence |\n|---|---|---|\n'
    for l in "${listed[@]}"; do
      IFS=$'\t' read -r key sha file <<<"$l"
      printf '| %s | %s | %s |\n' "$key" "$sha" "${file:--}"
    done
    printf '\n'
  fi

  printf '## Render pairs\n\n'
  any=0
  for l in "${listed[@]+"${listed[@]}"}"; do
    key="${l%%$'\t'*}"
    [ -d "$dir/evidence/$key" ] || continue
    any=1
    printf '### %s\n\n' "$key"
    printf '![%s reference](evidence/%s/reference.png) ![%s app](evidence/%s/app.png)\n\n' "$key" "$key" "$key" "$key"
    if [ -f "$dir/evidence/$key/verdict.md" ]; then
      printf 'Verdict:\n\n'
      tr -d '\r' <"$dir/evidence/$key/verdict.md" | sed 's/^/> /'
      printf '\n'
    fi
  done
  [ "$any" -eq 1 ] || printf 'No render pairs.\n\n'

  printf '## Evidence\n\n'
  any=0
  for l in "${listed[@]+"${listed[@]}"}"; do
    IFS=$'\t' read -r key sha file <<<"$l"
    [ -n "$file" ] || continue
    any=1
    printf '### %s\n\n' "$key"
    evidence_lines "$file"
    printf '\n'
  done
  [ "$any" -eq 1 ] || printf 'No evidence files.\n\n'

  printf '## Unverified\n\n'
  if [ "${#unverified[@]}" -eq 0 ]; then
    printf 'Nothing.\n'
  else
    for u in "${unverified[@]}"; do printf -- '- %s\n' "$u"; done
  fi
} >"$md" || fail "cannot write $md"

{
  printf '<!doctype html>\n<html><head><meta charset="utf-8"><title>%s</title>\n' "$(printf '%s' "$title" | esc)"
  printf '<style>body{font-family:sans-serif;margin:2em;max-width:1400px}table{border-collapse:collapse}'
  printf 'td,th{border:1px solid #bbb;padding:.3em .6em}.pair{display:flex;gap:1em}.pair figure{flex:1;margin:0}'
  printf '.pair img{max-width:100%%;border:1px solid #bbb}blockquote{color:#333;border-left:3px solid #bbb;margin-left:0;padding-left:1em}</style>\n'
  printf '</head><body>\n<h1>%s</h1>\n' "$(printf '%s' "$title" | esc)"
  printf '<p><em>Written by review.sh from board.md and the evidence files. It sends no notification; the orchestrator does.</em></p>\n'

  printf '<h2>Merged</h2>\n'
  if [ "${#listed[@]}" -eq 0 ]; then
    printf '<p>No rows merged since the previous packet.</p>\n'
  else
    printf '<table><tr><th>Key</th><th>Sha</th><th>Evidence</th></tr>\n'
    for l in "${listed[@]}"; do
      IFS=$'\t' read -r key sha file <<<"$l"
      printf '<tr><td>%s</td><td>%s</td><td>%s</td></tr>\n' \
        "$(printf '%s' "$key" | esc)" "$(printf '%s' "$sha" | esc)" "$(printf '%s' "${file:--}" | esc)"
    done
    printf '</table>\n'
  fi

  printf '<h2>Render pairs</h2>\n'
  any=0
  for l in "${listed[@]+"${listed[@]}"}"; do
    key="${l%%$'\t'*}"
    [ -d "$dir/evidence/$key" ] || continue
    any=1
    k="$(printf '%s' "$key" | esc)"
    printf '<h3>%s</h3>\n<div class="pair">' "$k"
    printf '<figure><img src="evidence/%s/reference.png" alt="%s reference"><figcaption>reference</figcaption></figure>' "$k" "$k"
    printf '<figure><img src="evidence/%s/app.png" alt="%s app"><figcaption>app</figcaption></figure></div>\n' "$k" "$k"
    if [ -f "$dir/evidence/$key/verdict.md" ]; then
      printf '<p>Verdict:</p><blockquote><pre>%s</pre></blockquote>\n' "$(tr -d '\r' <"$dir/evidence/$key/verdict.md" | esc)"
    fi
  done
  [ "$any" -eq 1 ] || printf '<p>No render pairs.</p>\n'

  printf '<h2>Evidence</h2>\n'
  any=0
  for l in "${listed[@]+"${listed[@]}"}"; do
    IFS=$'\t' read -r key sha file <<<"$l"
    [ -n "$file" ] || continue
    any=1
    printf '<h3>%s</h3>\n<ul>\n' "$(printf '%s' "$key" | esc)"
    evidence_lines "$file" | sed 's/^- //' | esc | sed 's/^/<li>/; s/$/<\/li>/'
    printf '</ul>\n'
  done
  [ "$any" -eq 1 ] || printf '<p>No evidence files.</p>\n'

  printf '<h2>Unverified</h2>\n'
  if [ "${#unverified[@]}" -eq 0 ]; then
    printf '<p>Nothing.</p>\n'
  else
    printf '<ul>\n'
    for u in "${unverified[@]}"; do printf '<li>%s</li>\n' "$(printf '%s' "$u" | esc)"; done
    printf '</ul>\n'
  fi
  printf '</body></html>\n'
} >"$html" || fail "cannot write $html"

# On Git Bash the path is printed in the host's form (C:/...), which every tool there can open.
shown="$md"
command -v cygpath >/dev/null 2>&1 && shown="$(cygpath -m "$md")"
echo "REVIEW $shown"
