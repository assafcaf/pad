#!/usr/bin/env bash
# test-removal check for code-deleted. Args: <base> <head> <removed-file>, whose lines are
# <path> TAB <test name>. Prints the lines it explains: a test in a file deleted at <head>
# whose imported project modules (tracked at <base>) are all deleted, not moved, by <head>.
set -uo pipefail
base="$1"; head="$2"; removed="$3"
deleted="$(git diff --name-status -M --diff-filter=D "$base" "$head" | cut -f2)"

# modules <test file>: the dotted names its import lines reach. `from a.b import x, y` yields
# a.b, a.b.x and a.b.y; names that are not modules resolve to no file below and drop out.
modules() {
  git show "$base:$1" 2>/dev/null | tr -d '\r' | awk '
    /^[ \t]*from[ \t]+[A-Za-z_][A-Za-z0-9_.]*[ \t]+import[ \t]/ {
      line = $0; sub(/#.*/, "", line); gsub(/[()]/, " ", line)
      n = split(line, w, /[ \t,]+/); m = ""; seen = 0
      for (i = 1; i <= n; i++) {
        if (w[i] == "from") { m = w[i + 1]; continue }
        if (w[i] == "import") { seen = 1; print m; continue }
        if (seen && w[i] != "" && w[i] != "as" && w[i - 1] != "as") print m "." w[i]
      }
      next
    }
    /^[ \t]*import[ \t]+[A-Za-z_]/ {
      line = $0; sub(/#.*/, "", line); sub(/^[ \t]*import[ \t]+/, "", line)
      n = split(line, w, /[ \t]*,[ \t]*/)
      for (i = 1; i <= n; i++) { split(w[i], p, /[ \t]+/); print p[1] }
    }' | sort -u
}

# explained <test file>: the file is gone and every project module it imported is too.
explained() {
  local f="$1" m c any=0
  git cat-file -e "$head:$f" 2>/dev/null && return 1
  for m in $(modules "$f"); do
    for c in "${m//.//}.py" "${m//.//}/__init__.py" "src/${m//.//}.py" "src/${m//.//}/__init__.py"; do
      git cat-file -e "$base:$c" 2>/dev/null || continue
      any=1
      printf '%s\n' "$deleted" | grep -qxF "$c" || return 1
    done
  done
  [ "$any" -eq 1 ]
}

ok=" "; bad=" "
while IFS=$'\t' read -r path name; do
  [ -n "$path" ] || continue
  if [[ "$bad" == *" $path "* ]]; then continue; fi
  if [[ "$ok" != *" $path "* ]]; then
    if explained "$path"; then ok="$ok$path "; else bad="$bad$path "; continue; fi
  fi
  printf '%s\t%s\n' "$path" "$name"
done <"$removed"
exit 0
