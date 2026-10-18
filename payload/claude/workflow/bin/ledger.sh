#!/usr/bin/env bash
# Write a ticket's status or a comment to the project's tracker, from any worktree or subdirectory.
#
#   ledger.sh <KEY> status <todo|doing|review|done> "<comment>" [board options]
#   ledger.sh <KEY> comment "<text>" [board options]
#
#   board options: --run <id> [--owner <agent id>] [--branch <b>] [--sha <s>] [--evidence <path>]
#
# The adapter is the config's Tracker → Adapter (`.claude/workflow/config.md` in this worktree,
# else in the main checkout); with no config it is `local`. PAD_LEDGER_ADAPTER, when set,
# overrides both.
#
#   local   <main checkout>/.work/tickets/<EPIC>/<KEY>.md, or .../<EPIC>/epic.md when KEY is an
#           epic key (E<n>). `status` rewrites the frontmatter `status:` line; both forms append
#           `- <yyyy-mm-dd>: <comment>` under `## Log`, creating the heading when missing.
#   github  `gh` against the current repository, KEY an issue number (`#12` or `12`). Statuses as
#           in trackers/github.md: doing and review are labels, done closes the issue.
#   jira    The Jira REST API at the config's site. The status is the configured name for <to>,
#           reached through the issue's transition with that `to.name`. Credentials come from
#           <main checkout>/.work/secrets/jira.env (gitignored with .work/): JIRA_EMAIL=… and
#           JIRA_API_TOKEN=… lines, read, never sourced or printed. Needs curl, and python or jq.
#
# With --run, the ticket's row in <main checkout>/.work/runs/<id>/board.md is written or
# refreshed: `| <KEY> | <owner> | <status> | <branch> | <sha> | <evidence> |`. A field not given
# keeps the row's earlier value (`-` for a new row).
#
# Last stdout line: `LEDGER OK <KEY> <status>`. Exit 1 with `LEDGER FAIL <KEY>: <why>` on
# stdout. Exit 64: usage.

set -uo pipefail

usage() {
  echo 'usage: ledger.sh <KEY> status <todo|doing|review|done> "<comment>" | ledger.sh <KEY> comment "<text>"  [--run <id> [--owner <id>] [--branch <b>] [--sha <s>] [--evidence <path>]]' >&2
  exit 64
}
fail() { echo "LEDGER FAIL $key: $1"; exit 1; }

pos=()
run="" owner="" br="" sha="" evidence=""
while [ $# -gt 0 ]; do
  case "$1" in
    --run|--owner|--branch|--sha|--evidence)
      [ $# -ge 2 ] || usage
      case "$1" in
        --run) run="$2" ;; --owner) owner="$2" ;; --branch) br="$2" ;;
        --sha) sha="$2" ;; --evidence) evidence="$2" ;;
      esac
      shift 2 ;;
    *) pos+=("$1"); shift ;;
  esac
done
[ "${#pos[@]}" -ge 3 ] || usage
key="${pos[0]}"; verb="${pos[1]}"
[ -n "$key" ] || usage
case "$verb" in
  status) [ "${#pos[@]}" -eq 4 ] || usage; to="${pos[2]}"; text="${pos[3]}" ;;
  comment) [ "${#pos[@]}" -eq 3 ] || usage; to=""; text="${pos[2]}" ;;
  *) usage ;;
esac

if [ "$verb" = status ]; then
  case "$to" in todo|doing|review|done) ;; *) fail "invalid status '$to' (todo|doing|review|done)" ;; esac
fi

top="$(git rev-parse --show-toplevel 2>/dev/null)" || fail "not a git repository"
main="$(cd "$top" && cd "$(git rev-parse --git-common-dir)/.." && pwd)" || fail "cannot find the main checkout"

cfg="$top/.claude/workflow/config.md"
[ -f "$cfg" ] || cfg="$main/.claude/workflow/config.md"
adapter="local"
if [ -f "$cfg" ]; then
  a="$(sed -n 's/^- \*\*Adapter:\*\* *`\([^`]*\)`.*/\1/p' "$cfg" | head -n 1)"
  # An unfilled `<TRACKER>` placeholder counts as unset.
  case "$a" in ''|'<'*) ;; *) adapter="$a" ;; esac
fi
# rehearse.sh sets local: its ticket is a throwaway file that no real tracker has.
[ -z "${PAD_LEDGER_ADAPTER:-}" ] || adapter="$PAD_LEDGER_ADAPTER"

# json_tool: the first of python / jq that runs here, for building and reading JSON.
json_tool() {
  local p
  for p in python python3; do
    "$p" -c 'import json' >/dev/null 2>&1 && { echo "$p"; return 0; }
  done
  command -v jq >/dev/null 2>&1 && { echo jq; return 0; }
  return 1
}

# --- local -------------------------------------------------------------------------------------
write_local() {
  # tmp is global: the EXIT trap that removes it runs after this function returns.
  local epic file line
  epic="${key%%-T*}"
  if [ "$epic" = "$key" ]; then file="$main/.work/tickets/$epic/epic.md"
  else file="$main/.work/tickets/$epic/$key.md"; fi
  [ -f "$file" ] || fail "no ticket at $file"

  tmp="$file.tmp.$$"
  trap 'rm -f "$tmp"' EXIT
  line="- $(date +%Y-%m-%d): $text"

  # Rewrite the first frontmatter `status:` line (status verb only), keep everything else.
  awk -v to="$to" '
    BEGIN { fm = 0; done = 0 }
    { sub(/\r$/, "") }
    NR == 1 && $0 == "---" { fm = 1; print; next }
    fm == 1 && $0 == "---" { fm = 2 }
    fm == 1 && !done && to != "" && /^status:/ { print "status: " to; done = 1; next }
    { print }
  ' "$file" >"$tmp" || fail "cannot read $file"

  # Make sure the file ends in a newline, then find or create the Log heading.
  [ -z "$(tail -c1 "$tmp")" ] || printf '\n' >>"$tmp"
  if ! grep -q '^## Log[[:space:]]*$' "$tmp"; then
    printf '\n## Log\n' >>"$tmp"
  fi
  printf '%s\n' "$line" >>"$tmp"

  cat "$tmp" >"$file" || fail "cannot write $file"

  cur="$(awk 'NR>1 && /^---$/ {exit} /^status:/ {sub(/^status:[ \t]*/, ""); sub(/[ \t#].*$/, ""); print; exit}' "$file")"
}

# --- github ------------------------------------------------------------------------------------
write_github() {
  local n="${key#\#}" out
  case "$n" in ''|*[!0-9]*) fail "not a GitHub issue number" ;; esac
  command -v gh >/dev/null 2>&1 || fail "gh is not installed"
  case "$to" in
    todo) out="$(gh issue edit "$n" --remove-label in-progress --remove-label in-review 2>&1)" ;;
    doing) out="$(gh issue edit "$n" --add-label in-progress --remove-label in-review 2>&1)" ;;
    review) out="$(gh issue edit "$n" --add-label in-review --remove-label in-progress 2>&1)" ;;
    done) out="$(gh issue close "$n" --reason completed 2>&1)" ;;
    *) out="" ;;
  esac || fail "gh status $to: $(printf '%s' "$out" | tail -n 1)"
  out="$(gh issue comment "$n" --body "$text" 2>&1)" ||
    fail "gh comment: $(printf '%s' "$out" | tail -n 1)"
  cur="${to:--}"
}

# --- jira --------------------------------------------------------------------------------------
# env_value <file> <NAME>: the value of a NAME=value line, quotes stripped.
env_value() {
  sed -n "s/^[[:space:]]*$2[[:space:]]*=[[:space:]]*//p" "$1" | head -n 1 | tr -d '\r' |
    sed "s/^[\"']//; s/[\"']\$//"
}

write_jira() {
  local site secrets email token jt name tid body out
  site="$(sed -n 's/^- \*\*Jira:\*\* site `\([^`]*\)`.*/\1/p' "$cfg" | head -n 1)"
  site="${site%/}"
  case "$site" in https://*) ;; *) fail "no Jira site in $cfg (Tracker → Jira)" ;; esac
  secrets="$main/.work/secrets/jira.env"
  [ -f "$secrets" ] || fail "no credentials: create $secrets with JIRA_EMAIL= and JIRA_API_TOKEN= lines"
  email="$(env_value "$secrets" JIRA_EMAIL)"
  token="$(env_value "$secrets" JIRA_API_TOKEN)"
  [ -n "$email" ] && [ -n "$token" ] || fail "$secrets needs JIRA_EMAIL and JIRA_API_TOKEN"
  command -v curl >/dev/null 2>&1 || fail "curl is not installed"
  jt="$(json_tool)" || fail "needs python or jq to read Jira's JSON"

  # The status of the last call; api runs in a command substitution, so it can't set a variable.
  codef="$(mktemp)"
  trap 'rm -f "$codef"' EXIT
  status_of() { cat "$codef" 2>/dev/null || echo '?'; }

  # api <method> <path> [<json body>]: the response body on stdout; fails on a non-2xx status.
  # The credentials go to curl on stdin (-K -), never on its command line.
  api() {
    local resp data=()
    [ $# -lt 3 ] || data=(-H 'Content-Type: application/json' --data "$3")
    echo '?' >"$codef"
    resp="$(printf 'user = "%s:%s"\n' "$email" "$token" |
      curl -sS -K - -X "$1" -H 'Accept: application/json' ${data[@]+"${data[@]}"} \
        -w '\n%{http_code}' "$site$2" 2>&1)" || return 1
    printf '%s' "$resp" | tail -n 1 | tr -d '\r' >"$codef"
    printf '%s\n' "$resp" | sed '$d'
    case "$(status_of)" in 2??) return 0 ;; *) return 1 ;; esac
  }

  if [ -n "$to" ]; then
    name="$(grep -m1 '^- \*\*Statuses:\*\*' "$cfg" | sed -n "s/.*[ ]$to \`\([^\`]*\)\`.*/\1/p")"
    [ -n "$name" ] || fail "no configured Jira status for '$to' (Tracker → Statuses)"
    out="$(api GET "/rest/api/3/issue/$key/transitions")" ||
      fail "transitions: HTTP $(status_of) $(printf '%s' "$out" | tail -n 1)"
    if [ "$jt" = jq ]; then
      tid="$(printf '%s' "$out" | jq -r --arg n "$name" '[.transitions[] | select(.to.name == $n) | .id][0] // empty')"
    else
      tid="$(printf '%s' "$out" | "$jt" -c 'import json,sys
n = sys.argv[1]
for t in json.load(sys.stdin).get("transitions", []):
    if t.get("to", {}).get("name") == n:
        print(t["id"]); break' "$name")"
    fi
    if [ -n "$tid" ]; then
      out="$(api POST "/rest/api/3/issue/$key/transitions" "{\"transition\":{\"id\":\"$tid\"}}")" ||
        fail "transition to $name: HTTP $(status_of) $(printf '%s' "$out" | tail -n 1)"
    else
      # Already there is fine; anything else is a workflow this config doesn't match.
      out="$(api GET "/rest/api/3/issue/$key?fields=status")" || fail "read status: HTTP $(status_of)"
      printf '%s' "$out" | grep -qF "\"name\":\"$name\"" ||
        fail "no transition to '$name' from the issue's current status"
    fi
  fi

  if [ "$jt" = jq ]; then
    body="$(jq -cn --arg t "$text" '{body: {type: "doc", version: 1, content: [{type: "paragraph", content: [{type: "text", text: $t}]}]}}')"
  else
    body="$("$jt" -c 'import json,sys
print(json.dumps({"body": {"type": "doc", "version": 1, "content": [
    {"type": "paragraph", "content": [{"type": "text", "text": sys.argv[1]}]}]}}))' "$text")"
  fi
  out="$(api POST "/rest/api/3/issue/$key/comment" "$body")" ||
    fail "comment: HTTP $(status_of) $(printf '%s' "$out" | tail -n 1)"
  cur="${to:--}"
}

# --- board -------------------------------------------------------------------------------------
# Write or refresh this ticket's row in the run's board.md; fields not given keep their value.
write_board() {
  local dir="$main/.work/runs/$run" file tmp
  file="$dir/board.md"
  mkdir -p "$dir" || fail "cannot create $dir"
  if [ ! -f "$file" ]; then
    printf '# Board: %s\n\n| Key | Owner | Status | Branch | Sha | Evidence |\n|---|---|---|---|---|---|\n' \
      "$run" >"$file" || fail "cannot write $file"
  fi
  tmp="$file.tmp.$$"
  awk -v k="$key" -v o="$owner" -v s="$cur" -v b="$br" -v h="$sha" -v e="$evidence" '
    function keep(new, old) { return new != "" ? new : (old != "" ? old : "-") }
    function trim(x) { gsub(/^[ \t]+|[ \t]+$/, "", x); return x }
    { sub(/\r$/, "") }
    /^\|/ {
      n = split($0, f, "|")
      if (n >= 8 && trim(f[2]) == k) {
        print "| " k " | " keep(o, trim(f[3])) " | " keep(s, trim(f[4])) " | " keep(b, trim(f[5])) \
          " | " keep(h, trim(f[6])) " | " keep(e, trim(f[7])) " |"
        found = 1; next
      }
    }
    { print }
    END {
      if (!found) print "| " k " | " keep(o, "") " | " keep(s, "") " | " keep(b, "") " | " keep(h, "") " | " keep(e, "") " |"
    }
  ' "$file" >"$tmp" && cat "$tmp" >"$file" || { rm -f "$tmp"; fail "cannot write $file"; }
  rm -f "$tmp"
}

cur=""
case "$adapter" in
  local) write_local ;;
  github) write_github ;;
  jira) write_jira ;;
  *) fail "unknown tracker adapter '$adapter' in $cfg (local|github|jira)" ;;
esac
# A comment leaves a board row's status as it was.
[ -z "$run" ] || { [ "$verb" = status ] || [ "$adapter" = local ] || cur=""; write_board; }
echo "LEDGER OK $key ${cur:--}"
