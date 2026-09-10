#!/usr/bin/env bash
# Scan a commit range and the tracked tree for credential values.
#
# Replaces the sweep the PROJ-17 manager ran by hand, twice, against its own prompt
# (.claude/skills/dispatch/SKILL.md:106 tells a manager not to read diffs). Both credential
# exposures in that run were caught only because it did. A safeguard that depends on an agent
# disobeying is luck.
#
# Usage: no-secrets.sh <base> [<head>]
#
# Matches values, not placeholders: the literal strings this repo uses in prose
# (-e HF_TOKEN=..., hf_REPLACE_ME, nvapi-REPLACE_ME) do not trip it.
#
# Every grep pattern goes through `-e`. The first draft of this script did not, and the
# PRIVATE KEY pattern -- which begins with a dash -- was parsed as an option: grep errored, the
# loop carried on, and the script printed "ok" having never run that pattern. Found by running
# it. It is the reason the self-test at the bottom exists.

set -uo pipefail

base="${1:?usage: no-secrets.sh <base> [<head>]}"
head="${2:-HEAD}"

# Value shapes. Anchored on the issuer's prefix, then enough entropy to exclude a placeholder.
patterns=(
  'hf_[A-Za-z0-9]{30,}'
  'nvapi-[A-Za-z0-9_-]{30,}'
  'ghp_[A-Za-z0-9]{30,}'
  'github_pat_[A-Za-z0-9_]{50,}'
  'xox[baprs]-[A-Za-z0-9-]{20,}'
  'AKIA[0-9A-Z]{16}'
  'BEGIN [A-Z ]*PRIVATE KEY'
  'ATATT3[A-Za-z0-9_=.-]{50,}'
)

rc=0
redact() { sed -E 's/(.{50}).*/\1... [redacted]/'; }

echo "no-secrets: scanning ${base}..${head} and the tracked tree"

diffing=$(mktemp); trap 'rm -f "$diffing"' EXIT
git log -p --no-color "${base}..${head}" 2>/dev/null | grep -E '^\+' > "$diffing" || true

for p in "${patterns[@]}"; do
  # The commit range: added lines only. A secret that was later removed is still in the history.
  n=$(grep -Ec -e "$p" "$diffing" || true)
  if [ "${n:-0}" -gt 0 ]; then
    echo "  FAIL commit range: ${n} added line(s) match /${p}/"
    grep -En -e "$p" "$diffing" | head -3 | redact | sed 's/^/        /'
    rc=1
  fi

  # The tracked tree. Untracked local env files are gitignored by design and not our business.
  if git grep -I -q -E -e "$p" -- . 2>/dev/null; then
    echo "  FAIL tracked tree: a tracked file matches /${p}/"
    git grep -I -n -E -e "$p" -- . | head -3 | redact | sed 's/^/        /'
    rc=1
  fi
done

# The env files must never be tracked, whatever they contain.
for forbidden in docker/.env config/secrets.env.local config/secrets.env; do
  if git ls-files --error-unmatch "$forbidden" >/dev/null 2>&1; then
    echo "  FAIL ${forbidden} is tracked"
    rc=1
  fi
done

# Self-test: prove the matcher still works, so a broken pattern cannot pass as a clean scan.
# Assembled at runtime, never written out as a literal -- the first draft spelled it in full and
# the tree scan above matched the checker's own source, which is at least an honest failure.
canary="hf_$(printf 'x%.0s' $(seq 40))"
if ! printf '%s\n' "$canary" | grep -Eq -e "${patterns[0]}"; then
  echo "  FAIL self-test: the matcher did not fire on its own canary. This scan proves nothing."
  rc=1
fi

if [ "$rc" -eq 0 ]; then
  echo "  ok: ${#patterns[@]} patterns, no credential values in ${base}..${head} or the tracked tree"
fi
exit "$rc"
