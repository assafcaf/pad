#!/usr/bin/env bash
# Every committed script with a shebang must be mode 100755.
#
# PROJ-17's final review, finding 6: five scripts were committed 100644, and three commands the
# docs told a newcomer to run failed on a fresh clone. It took an opus whole-branch review to
# find. It is one git command.
#
# Usage: exec-bits.sh
#
# The shebang is the discriminator, and it is the right one. `scripts/lib.sh` opens with
# "Shared helpers. Sourced, not executed." and every caller uses `. path` -- it has no shebang
# and must NOT be executable. A rule that demanded +x on every .sh would have raised a false
# finding against it on this repo's first run, which is the failure this whole process exists
# to avoid.
#
# Git stores only 100644 and 100755, so this is exact on every platform, including the Windows
# checkout where the filesystem has no execute bit to inspect.
#
# .claude/skills/ is excluded: those payloads are installed from mattpocock/skills and are not
# ours to chmod. CLAUDE.md records that four of them already report as locally modified.

set -uo pipefail

rc=0
missing=""
spurious=""
crlf=""

# A temp file, not `< <(git ls-files ...)`. Process substitution needs /dev/fd, which Git Bash
# on this Windows host does not provide -- the redirect fails, the loop body never runs, and the
# check reports "ok" having examined nothing. Found by running this script against its own
# commit, which is the entire argument for the red-then-green rule in
# docs/agents/evidence-dispatch.md.
listing=$(mktemp)
trap 'rm -f "$listing"' EXIT
git ls-files -s -- '*.sh' 'scripts/*' 'gates/*' > "$listing"

if [ ! -s "$listing" ]; then
  echo "exec-bits: FAIL -- git ls-files returned nothing. Not a repository, or no scripts."
  exit 1
fi

while IFS= read -r line; do
  mode="${line%% *}"
  path="${line#*$'\t'}"

  case "$path" in
    .claude/*) continue ;;
    *.template.sh) continue ;;
  esac
  [ "$mode" = "120000" ] && continue          # symlink
  git cat-file -e ":${path}" 2>/dev/null || continue

  first=$(git show ":${path}" 2>/dev/null | head -1)
  case "$first" in
    '#!'*)
      [ "$mode" = "100755" ] || missing="${missing}  ${mode}  ${path}"$'\n'
      # A CRLF line ending makes the shebang `/usr/bin/env bash\r`, and Linux answers
      # "bad interpreter: No such file or directory". This repo edits on Windows and executes
      # on the box, so the committed blob is what matters, not the working copy.
      if git show ":${path}" 2>/dev/null | head -1 | grep -q $'\r'; then
        crlf="${crlf}  ${path}"$'\n'
      fi
      ;;
    *)
      [ "$mode" = "100755" ] && spurious="${spurious}  ${mode}  ${path}"$'\n'
      ;;
  esac
done < "$listing"

if [ -n "$missing" ]; then
  echo "exec-bits: FAIL -- scripts with a shebang but no execute bit"
  printf '%s' "$missing"
  echo "  A documented command that starts with ./ fails for anyone who has not chmod'd it."
  echo "  fix: git update-index --chmod=+x <path>   (then commit)"
  rc=1
fi

if [ -n "$spurious" ]; then
  echo "exec-bits: FAIL -- executable files with no shebang"
  printf '%s' "$spurious"
  echo "  Either it is meant to be sourced, in which case drop the bit, or it is missing its"
  echo "  shebang and will run under whatever shell happens to invoke it."
  echo "  fix: git update-index --chmod=-x <path>   (then commit)"
  rc=1
fi

if [ -n "$crlf" ]; then
  echo "exec-bits: FAIL -- shebang'd scripts committed with CRLF line endings"
  printf '%s' "$crlf"
  echo "  Linux reads the shebang as /usr/bin/env bash\r and answers 'bad interpreter'."
  echo "  fix: add the path to .gitattributes with 'text eol=lf', then re-add the file."
  rc=1
fi

if [ "$rc" -eq 0 ]; then
  n=$(git ls-files -- '*.sh' 'scripts/*' 'gates/*' | grep -vc '^\.claude/' || true)
  echo "exec-bits: ok -- ${n} committed script(s), every shebang'd one is 100755"
fi

exit "$rc"
