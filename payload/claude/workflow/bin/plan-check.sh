#!/usr/bin/env bash
# Lint a ticket set before it runs: who owns what, what is shared, what is protected, and
# which chain of dependencies decides how long the epic takes.
#
#   plan-check.sh <plan file | ticket dir> [--protected "<globs>"] [--churn <n>] [--max-dirs <n>]
#   plan-check.sh --list <ticket file>
#
# Input: a plan file, where each ticket is a `### <KEY> — <title>` section holding the ticket
# body, or a directory of `<KEY>.md` ticket files (a YAML frontmatter `key:` overrides the
# file name). The body sections read are `## Owns` and `## Touches` (bullets; a path may be
# backticked, and a trailing `(note)` is dropped), `## Protected` (yes | no) and `## Depends on`
# (keys; `## Blocked by`, or frontmatter `blocked_by:` / `depends_on:`, are read the same way).
# A path ending in `/` names a directory, and covers everything below it.
#
# Protected globs come from the `## Protected paths` section of .claude/workflow/config.md at
# the top of the current repository (one backticked glob per bullet; no section = none), or
# from --protected, whitespace- or comma-separated, which replaces them.
#
# One finding per line, each starting with its section word, in this order:
#   OVERLAPS <K1> <K2>: <path>[ (inside <dir>)]   an Owns path of K1 equals or nests in K2's
#   HOTSPOTS shared: <path> (<K1> <K2> <K3>...)    a Touches path shared by more than 2 tickets
#   HOTSPOTS churn: <path> (<n> of the last 200 commits)   an Owns/Touches path changed in more
#                                                  than --churn commits (default 10)
#   PROTECTED <K>: <path> matches <glob> but Protected: <no|missing>
#   DEPENDS <K>: unknown key <X>  |  DEPENDS cycle: <K1> -> <K2> -> <K1>
#   CRITICAL-PATH <K1> -> <K2> -> ...              the longest Depends-on chain, first to land
#                                                  first (omitted when there is a cycle)
#   SWEEPS <K>: <n> top-level dirs (<d1> <d2>...)  Owns spans more than --max-dirs (default 3)
# HOTSPOTS and SWEEPS are warnings. Last line: PLAN OK, or PLAN FAIL <n>, where n counts the
# OVERLAPS, PROTECTED and DEPENDS lines.
#
# Spec domains (plan files only): a `Spec: <path>` line before the first ticket names the spec;
# its `## Domains` bullets (`- name: ...` or `- **name**: ...`) are the domains. Each ticket names
# one in `## Domain`; a domain with more than one ticket needs a `## Split` on each of them, naming
# `independent-surface`, `parallel-by-interface`, `split-after-failures` or `operator "<words>"`.
#   DOMAIN <K>: unknown <name>   DOMAIN <name>: no ticket   SPLIT <name>: <n> tickets
#   SPLIT <name>: <K1> <K2> (<reason>)   a valid split, printed for the approval table
#   DOMAIN skipped: <why>        no Spec: line, or the spec has no ## Domains (not a failure)
# The first three count toward PLAN FAIL.
#
# --list prints one ticket's paths, `OWNS <path>` then `TOUCHES <path>`, one per line; it is
# how task-submit.sh reads a ticket, so both read paths the same way.
#
# Exit 0: PLAN OK (or --list done). Exit 1: PLAN FAIL. Exit 64: usage.

set -uo pipefail

usage() {
  echo "usage: plan-check.sh <plan file | ticket dir> [--protected \"<globs>\"] [--churn <n>] [--max-dirs <n>] | plan-check.sh --list <ticket file>" >&2
  exit 64
}

input="" list="" protected="" have_protected="" churn=10 maxdirs=3
while [ $# -gt 0 ]; do
  case "$1" in
    --list) [ $# -ge 2 ] || usage; list="$2"; shift 2 ;;
    --protected) [ $# -ge 2 ] || usage; protected="$2"; have_protected=1; shift 2 ;;
    --churn) [ $# -ge 2 ] || usage; churn="$2"; shift 2 ;;
    --max-dirs) [ $# -ge 2 ] || usage; maxdirs="$2"; shift 2 ;;
    -*) usage ;;
    *) [ -z "$input" ] || usage; input="$1"; shift ;;
  esac
done
case "$churn$maxdirs" in *[!0-9]*) usage ;; esac
[ -n "$churn" ] && [ -n "$maxdirs" ] || usage

tmp="$(mktemp -d)" || exit 1
trap 'rm -rf "$tmp"' EXIT

# parse <mode> <default key> <file>: records, tab-separated, on stdout:
#   T <key> | O <key> <path> | H <key> <path> | P <key> <yes|no|...> | D <key> <dep key>
# mode "plan": tickets are `### <KEY>` sections; mode "file": one ticket, key from the name or
# the frontmatter.
parse() {
  awk -v mode="$1" -v key="$2" '
    function path(s,   w) {
      sub(/^[ \t]*[-*+][ \t]+/, "", s)
      if (match(s, /`[^`]+`/)) s = substr(s, RSTART + 1, RLENGTH - 2)
      else { sub(/[ \t]+\(.*$/, "", s); sub(/^[ \t]+/, "", s); split(s, w, /[ \t]+/); s = w[1] }
      sub(/^\.\//, "", s)
      while (length(s) > 1 && s ~ /\/$/) sub(/\/$/, "", s)
      return s
    }
    function deps(s,   n, i, w) {
      sub(/^[ \t]*[-*+][ \t]+/, "", s); gsub(/\([^)]*\)/, "", s); gsub(/[`"\047\[\]]/, "", s)
      n = split(s, w, /[ \t,;]+/)
      for (i = 1; i <= n; i++)
        if (w[i] ~ /^[A-Za-z0-9][A-Za-z0-9_.-]*$/ && w[i] ~ /[0-9]/) out("D", w[i])
    }
    function out(kind, v) { if (cur != "") print kind "\t" cur (v == "" ? "" : "\t" v) }
    function start() { if (!started && cur != "") { print "T\t" cur; started = 1 } }
    BEGIN { cur = (mode == "file") ? key : ""; fm = 0; fence = 0 }
    { sub(/\r$/, "") }
    mode == "plan" && cur == "" && /^Spec:[ \t]*/ && !specseen {
      s = $0; sub(/^Spec:[ \t]*/, "", s); gsub(/[`"\047]/, "", s); sub(/[ \t]+$/, "", s)
      print "X\t-\t" s; specseen = 1; next
    }
    mode == "file" && FNR == 1 && /^---[ \t]*$/ { fm = 1; next }
    fm == 1 {
      if (/^---[ \t]*$/) { fm = 2; next }
      if (match($0, /^key:[ \t]*/)) { cur = substr($0, RLENGTH + 1); gsub(/["\047 \t]/, "", cur) }
      else if (match($0, /^(blocked_by|depends_on):[ \t]*/)) fmdeps = fmdeps " " substr($0, RLENGTH + 1)
      next
    }
    mode == "file" { start(); if (fmdeps != "") { deps(fmdeps); fmdeps = "" } }
    /^[ \t]*(```|~~~)/ { fence = !fence; next }
    fence { next }
    mode == "plan" && /^### / {
      cur = $2; sub(/:$/, "", cur); started = 0; start(); sec = ""; next
    }
    /^#+ / {
      h = tolower($0); sub(/^#+[ \t]+/, "", h); sub(/[ \t]+$/, "", h)
      sec = (h == "owns") ? "O" : (h == "touches") ? "H" : (h == "protected") ? "P" \
          : (h == "domain") ? "M" : (h == "split") ? "S" \
          : (h == "depends on" || h == "blocked by") ? "D" : ""
      done = 0
      next
    }
    sec == "M" || sec == "S" {
      if (NF && !done) {
        v = $0; sub(/^[ \t]*[-*+][ \t]+/, "", v); sub(/^[ \t]+/, "", v); sub(/[ \t]+$/, "", v)
        if (sec == "M") { gsub(/[`*_]/, "", v); sub(/[ \t].*$/, "", v) }
        out(sec, v); done = 1
      }
      next
    }
    sec == "O" || sec == "H" {
      if ($0 !~ /^[ \t]*[-*+][ \t]+/) next
      p = path($0)
      if (p != "" && tolower(p) !~ /^(none|n\/a|-)$/) out(sec, p)
      next
    }
    sec == "P" && NF {
      v = tolower($1); gsub(/[`*_]/, "", v); out("P", v); sec = ""; next
    }
    sec == "D" && NF { deps($0) }
    END { if (mode == "file") start() }
  ' "$3"
}

if [ -n "$list" ]; then
  [ -z "$input" ] && [ -f "$list" ] || usage
  base="$(basename "$list")"
  parse file "${base%.md}" "$list" | awk -F '\t' '
    $1 == "O" { print "OWNS " $3 } $1 == "H" { t[++n] = "TOUCHES " $3 }
    END { for (i = 1; i <= n; i++) print t[i] }'
  exit 0
fi

[ -n "$input" ] || usage
recs="$tmp/recs"
if [ -d "$input" ]; then
  : >"$recs"
  for f in "$input"/*.md; do
    [ -f "$f" ] || continue
    base="$(basename "$f")"
    parse file "${base%.md}" "$f" >>"$recs"
  done
elif [ -f "$input" ]; then
  parse plan "" "$input" >"$recs"
else
  echo "plan-check: no such file or directory: $input" >&2
  usage
fi

if ! grep -q '^T' "$recs"; then
  echo "plan-check: no tickets found in $input" >&2
  echo "PLAN FAIL 1"
  exit 1
fi

# Overlaps, shared Touches, sweeps, unknown keys, cycles and the critical path.
awk -F '\t' -v dir="$tmp" -v maxdirs="$maxdirs" '
  function visit(k,   i, d, l, best, j, c) {
    if (state[k] == 2) return len[k]
    if (state[k] == 1) {
      for (j = sp; j >= 1 && stack[j] != k; j--) ;
      c = k; for (j = j + 1; j <= sp; j++) c = c " -> " stack[j]
      print "DEPENDS cycle: " c " -> " k > (dir "/depends"); cyc = 1
      return 0
    }
    state[k] = 1; stack[++sp] = k; best = 0; nxt[k] = ""
    for (i = 1; i <= nd[k]; i++) {
      d = dep[k, i]
      if (!(d in known)) continue
      l = visit(d)
      if (l > best) { best = l; nxt[k] = d }
    }
    sp--; state[k] = 2; len[k] = best + 1
    return len[k]
  }
  $1 == "T" { if (!($2 in known)) { known[$2] = 1; keys[++nk] = $2 } next }
  $1 == "O" { if (!(($2, $3) in seen)) { seen[$2, $3] = 1; own[$2, ++no[$2]] = $3 } next }
  $1 == "H" {
    if (!($3 in tk)) { tpaths[++nt] = $3; tk[$3] = "" }
    if (!(($2, $3, "h") in seen)) { seen[$2, $3, "h"] = 1; tk[$3] = tk[$3] " " $2; tn[$3]++ }
    next
  }
  $1 == "D" { dep[$2, ++nd[$2]] = $3; next }
  END {
    for (i = 1; i <= nk; i++) for (j = i + 1; j <= nk; j++) {
      a = keys[i]; b = keys[j]
      for (x = 1; x <= no[a]; x++) for (y = 1; y <= no[b]; y++) {
        p = own[a, x]; q = own[b, y]
        if (p == q) f = p
        else if (index(q, p "/") == 1) f = q " (inside " p ")"
        else if (index(p, q "/") == 1) f = p " (inside " q ")"
        else continue
        print "OVERLAPS " a " " b ": " f > (dir "/overlaps")
      }
    }
    for (i = 1; i <= nt; i++)
      if (tn[tpaths[i]] > 2) print "HOTSPOTS shared: " tpaths[i] " (" substr(tk[tpaths[i]], 2) ")" > (dir "/hotspots")
    for (i = 1; i <= nk; i++) {
      k = keys[i]
      for (j = 1; j <= nd[k]; j++)
        if (!(dep[k, j] in known)) print "DEPENDS " k ": unknown key " dep[k, j] > (dir "/depends")
    }
    top = 0; first = ""
    for (i = 1; i <= nk; i++) { l = visit(keys[i]); if (l > top) { top = l; first = keys[i] } }
    if (!cyc && first != "") {
      c = first; k = first
      while (nxt[k] != "") { k = nxt[k]; c = k " -> " c }
      print "CRITICAL-PATH " c > (dir "/critical")
    }
    for (i = 1; i <= nk; i++) {
      k = keys[i]; n = 0; list = ""; split("", tops)
      for (x = 1; x <= no[k]; x++) {
        d = own[k, x]; if (index(d, "/")) d = substr(d, 1, index(d, "/") - 1); else d = "."
        if (!(d in tops)) { tops[d] = 1; n++; list = list " " d }
      }
      if (n > maxdirs) print "SWEEPS " k ": " n " top-level dirs (" substr(list, 2) ")" > (dir "/sweeps")
    }
  }' "$recs"

# Churn: Owns/Touches paths changed in more than $churn of the last 200 commits.
if git rev-parse --git-dir >/dev/null 2>&1; then
  awk -F '\t' '($1 == "O" || $1 == "H") && !seen[$3]++ { print $3 }' "$recs" >"$tmp/paths"
  git log --name-only -n 200 --pretty=tformat:@@ 2>/dev/null | awk -v churn="$churn" '
    function flush(   p) { for (p in hit) count[p]++; split("", hit) }
    NR == FNR { paths[++np] = $0; next }
    /^@@$/ { flush(); next }
    NF { for (i = 1; i <= np; i++) if ($0 == paths[i] || index($0, paths[i] "/") == 1) hit[paths[i]] = 1 }
    END {
      flush()
      for (i = 1; i <= np; i++)
        if (count[paths[i]] > churn) print "HOTSPOTS churn: " paths[i] " (" count[paths[i]] " of the last 200 commits)"
    }' "$tmp/paths" - >>"$tmp/hotspots"
fi

# Protected: a ticket whose Owns or Touches hits a protected glob must say Protected: yes.
if [ -z "$have_protected" ]; then
  top="$(git rev-parse --show-toplevel 2>/dev/null)" || top="."
  cfg="$top/.claude/workflow/config.md"
  if [ -f "$cfg" ]; then
    protected="$(awk '
      { sub(/\r$/, "") }
      /^## / { on = ($0 ~ /^## Protected paths[ \t]*$/); next }
      on && /^[ \t]*[-*+][ \t]/ && match($0, /`[^`]+`/) { print substr($0, RSTART + 1, RLENGTH - 2) }
    ' "$cfg")"
  fi
fi
globs=()
set -f  # the globs are patterns, not files to expand
for g in ${protected//,/ }; do globs+=("$g"); done
set +f

# hits <path> <glob>: the path matches the glob, or is a directory that holds what it names.
hits() {
  local p="$1" g="$2" lit
  # shellcheck disable=SC2053
  [[ $p == $g || $p/ == $g ]] && return 0
  # shellcheck disable=SC2053
  [[ $g == '**/'* && $p == ${g#'**/'} ]] && return 0
  lit="${g%%[*?[]*}"
  lit="${lit%/}"
  [ -n "$lit" ] && [[ $lit == "$p" || $lit == "$p"/* ]]
}

if [ "${#globs[@]}" -gt 0 ]; then
  keys="$(awk -F '\t' '$1 == "T" && !seen[$2]++ { print $2 }' "$recs")"
  for k in $keys; do
    said="$(awk -F '\t' -v k="$k" '$1 == "P" && $2 == k { print $3; exit }' "$recs")"
    [ "$said" = yes ] && continue
    found=""
    while IFS=$'\t' read -r kind key p; do
      [ "$key" = "$k" ] && { [ "$kind" = O ] || [ "$kind" = H ]; } || continue
      for g in "${globs[@]}"; do
        if hits "$p" "$g"; then found="$p matches $g"; break; fi
      done
      [ -z "$found" ] || break
    done <"$recs"
    [ -z "$found" ] || echo "PROTECTED $k: $found but Protected: ${said:-missing}" >>"$tmp/protected"
  done
fi

# Domains: the spec's domains bind the ticket split.
specpath="$(awk -F '\t' '$1 == "X" { print $3; exit }' "$recs")"
if [ -z "$specpath" ]; then
  echo "DOMAIN skipped: no Spec: line in the plan" >"$tmp/domains-info"
elif [ ! -f "$specpath" ]; then
  echo "DOMAIN skipped: spec $specpath not found" >"$tmp/domains-info"
else
  awk '
    { sub(/\r$/, "") }
    /^## / { on = ($0 ~ /^## Domains[ \t]*$/); next }
    on && /^[ \t]*[-*+][ \t]+/ {
      s = $0; sub(/^[ \t]*[-*+][ \t]+/, "", s); gsub(/[`*_]/, "", s); sub(/[ \t]*[:(].*$/, "", s)
      sub(/[ \t]+.*$/, "", s); if (s != "") print s
    }' "$specpath" >"$tmp/specdomains"
  if [ ! -s "$tmp/specdomains" ]; then
    echo "DOMAIN skipped: spec $specpath has no ## Domains" >"$tmp/domains-info"
  else
    awk -F '\t' -v dir="$tmp" '
      FILENAME == ARGV[1] { dom[$0] = 1; order[++nd] = $0; next }
      $1 == "T" { if (!($2 in kn)) { kn[$2] = 1; keys[++nk] = $2 } next }
      $1 == "M" { mine[$2] = $3; next }
      $1 == "S" { spl[$2] = $3; next }
      END {
        for (i = 1; i <= nk; i++) {
          k = keys[i]
          if (!(k in mine) || !(mine[k] in dom)) {
            print "DOMAIN " k ": unknown " ((k in mine) ? mine[k] : "(no ## Domain section)") > (dir "/domains")
            continue
          }
          d = mine[k]; cnt[d]++; members[d] = members[d] " " k
        }
        for (i = 1; i <= nd; i++) {
          d = order[i]
          if (!cnt[d]) { print "DOMAIN " d ": no ticket" > (dir "/domains"); continue }
          if (cnt[d] < 2) continue
          n = split(substr(members[d], 2), m, " "); ok = 1; reason = ""
          for (j = 1; j <= n; j++) {
            s = spl[m[j]]; r = s; sub(/[ \t].*$/, "", r)
            if (r == "operator") { if (s !~ /"[^"]+"/) ok = 0 }
            else if (r != "independent-surface" && r != "parallel-by-interface" && r != "split-after-failures") ok = 0
            if (j == 1) reason = r
          }
          if (ok) print "SPLIT " d ": " substr(members[d], 2) " (" reason ")" > (dir "/splits")
          else print "SPLIT " d ": " cnt[d] " tickets" > (dir "/domains")
        }
      }' "$tmp/specdomains" "$recs"
  fi
fi

for part in overlaps hotspots protected depends domains-info domains splits critical sweeps; do
  [ -f "$tmp/$part" ] && cat "$tmp/$part"
done
bad="$(cat "$tmp/overlaps" "$tmp/protected" "$tmp/depends" "$tmp/domains" 2>/dev/null | grep -c .)"
if [ "$bad" -gt 0 ]; then
  echo "PLAN FAIL $bad"
  exit 1
fi
echo "PLAN OK"
