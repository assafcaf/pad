#!/usr/bin/env bash
# Attach evidence files to a Jira issue.
#
# The atlassian MCP server has no attachment tool -- fetch is read-only by ARI and
# addCommentToJiraIssue takes only a body -- so images and logs go up over REST.
#
# Usage:
#   scripts/jira-attach.sh PROJ-41 evidence/PROJ-40/PROJ-41/2-serves.log frame-000.png
#
# Requires JIRA_EMAIL and JIRA_API_TOKEN in the environment. Token from
# https://id.atlassian.com/manage-profile/security/api-tokens
#
# Exit codes:
#   0  every file attached
#   2  credentials absent -- NOT an error. The caller falls back to naming each artifact's
#      committed path and sha256 in the comment, and says attachment was unavailable. It does
#      not claim an attachment it did not make.
#   1  a request failed
#
# The credentials never reach a command line. PROJ-17 leaked two secrets by the same mechanism --
# a diagnostic that printed a process's or a stack's resolved configuration -- and the manager's
# PROJ-30 ruling recorded it as a class, not two accidents. curl reads them from stdin here, so
# `ps aux` shows nothing.

set -uo pipefail

SITE="${JIRA_SITE:?set JIRA_SITE, e.g. https://your-site.atlassian.net}"

issue="${1:-}"
shift || true

if [ -z "$issue" ] || [ $# -eq 0 ]; then
  echo "usage: jira-attach.sh <ISSUE-KEY> <file> [<file> ...]" >&2
  exit 64
fi

if [ -z "${JIRA_EMAIL:-}" ] || [ -z "${JIRA_API_TOKEN:-}" ]; then
  echo "jira-attach: JIRA_EMAIL / JIRA_API_TOKEN not set -- attachment unavailable." >&2
  echo "  Name each artifact's committed path and sha256 in the comment instead, and say so." >&2
  exit 2
fi

rc=0
for f in "$@"; do
  if [ ! -f "$f" ]; then
    echo "jira-attach: no such file: $f" >&2
    rc=1
    continue
  fi

  # -K - reads the auth line from stdin, keeping it off the process table.
  status=$(printf 'user = "%s:%s"\n' "$JIRA_EMAIL" "$JIRA_API_TOKEN" | curl -sS -K - \
      -X POST \
      -H "X-Atlassian-Token: no-check" \
      -H "Accept: application/json" \
      -F "file=@${f}" \
      -o /tmp/jira-attach-$$.json \
      -w '%{http_code}' \
      "${SITE}/rest/api/3/issue/${issue}/attachments")

  if [ "$status" = "200" ] || [ "$status" = "201" ]; then
    echo "jira-attach: ${issue} <- $(basename "$f")"
  else
    echo "jira-attach: FAILED ${status} for $(basename "$f")" >&2
    head -c 400 /tmp/jira-attach-$$.json >&2 2>/dev/null || true
    echo >&2
    rc=1
  fi
  rm -f /tmp/jira-attach-$$.json
done

exit "$rc"
