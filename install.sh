#!/usr/bin/env bash
# Install the dispatch skills into a project, and write their per-project configuration.
#
# The skills in payload/claude/skills read their configuration from docs/agents/*.md — which
# issue tracker, which project key, which site. Those files cannot be shipped filled in, so
# this asks and writes them. Everything it asks can be answered up front with a flag instead,
# which is what makes an unattended install possible.
#
#   bash install.sh [options]
#
#     --project <path>      project to install into            (default: current directory)
#     --tracker <kind>      jira | github | obsidian | other   (asked if not given)
#     --key <PROJ>          issue key prefix, e.g. PROJ        (asked unless tracker is other)
#     --jira-site <name>    the <name> in <name>.atlassian.net (jira)
#     --jira-cloud-id <id>  Jira cloud id, blank if unknown    (jira)
#     --gh-repo <o/r>       owner/repo                         (github; defaults from `gh`)
#     --vault <path>        absolute path to the vault         (obsidian)
#     --no-config           install the skills, write no docs/agents files
#     --force               overwrite existing files without keeping a .bak
#     --dry-run             print every action, change nothing
#
# Existing docs/agents/*.md are never overwritten — they are yours, and a reinstall should not
# silently revert a file you have edited. Delete one to have it regenerated.
#
# Re-running is safe: identical files are skipped.

set -u

SELF="dispatch-skills"
SRC="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/payload"

project="$PWD"
tracker=""
jira_site=""
jira_cloud=""
key=""
gh_repo=""
vault=""
do_config=yes
force=no
dry=no
changed=0
skipped=0

while [ $# -gt 0 ]; do
  case "$1" in
    --project)       project="${2-}"; shift 2 ;;
    --tracker)       tracker="${2-}"; shift 2 ;;
    --jira-site)     jira_site="${2-}"; shift 2 ;;
    --jira-cloud-id) jira_cloud="${2-}"; shift 2 ;;
    --key)           key="${2-}"; shift 2 ;;
    --gh-repo)       gh_repo="${2-}"; shift 2 ;;
    --vault)         vault="${2-}"; shift 2 ;;
    --no-config)     do_config=no; shift ;;
    --force)         force=yes; shift ;;
    --dry-run)       dry=yes; shift ;;
    -h|--help)       sed -n '2,24p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) printf '%s: unknown option %s\n' "$SELF" "$1" >&2; exit 2 ;;
  esac
done

say()  { printf '%s\n' "$*"; }
act()  { if [ "$dry" = yes ]; then printf '  would %s\n' "$*"; else printf '  %s\n' "$*"; fi; }
warn() { printf '%s: %s\n' "$SELF" "$*" >&2; }
die()  { warn "$1"; exit 1; }

[ -d "$SRC" ] || die "payload missing: $SRC"
[ -d "$project" ] || die "no such directory: $project"
project="$(cd -- "$project" && pwd)"

case "$tracker" in ''|jira|github|obsidian|other) ;; *)
  die "--tracker must be jira, github, obsidian or other (got '$tracker')" ;;
esac

say "$SELF -> $project"

# --- Files --------------------------------------------------------------------------------
install_file() {
  local rel="$1" src="$SRC/$1" dst="$project/${2:-$1}"
  [ -f "$src" ] || { warn "missing from payload: $rel"; return 1; }

  if [ -f "$dst" ] && cmp -s "$src" "$dst"; then
    skipped=$((skipped + 1)); return 0
  fi
  if [ -f "$dst" ] && [ "$force" = no ] && [ ! -f "$dst.bak" ]; then
    act "back up ${2:-$1} -> ${2:-$1}.bak"
    [ "$dry" = yes ] || cp "$dst" "$dst.bak" || return 1
  fi
  act "install ${2:-$1}"
  if [ "$dry" = no ]; then
    mkdir -p "$(dirname "$dst")" || return 1
    cp "$src" "$dst" || return 1
    case "$rel" in *.sh) chmod +x "$dst" ;; esac
  fi
  changed=$((changed + 1))
}

say ""
say "Skills -> .claude/skills/"
# The two dispatch skills, then the four they reach for. dispatch's worker reads
# implement/SKILL.md and runs /review-standards-spec; its integrator reaches for
# /resolving-merge-conflicts; evidence-dispatch's planner and worker read tdd/SKILL.md.
for f in $(cd "$SRC" && find claude/skills -type f -name '*.md' | sort); do
  install_file "$f" ".claude/${f#claude/}"
done

say ""
say "Checks -> scripts/"
for f in $(cd "$SRC" && find scripts/checks -type f | sort); do
  install_file "$f" "$f"
done
# scripts/jira-attach.sh is installed further down, once the tracker is known — copying it
# here would drop a Jira helper into an Obsidian project.

# --- Configuration ------------------------------------------------------------------------
# docs/agents/*.md is what makes these skills fit a particular repo. Generated from the
# .example.md templates with the answers below substituted in.
ask() { # ask <prompt> <default> -> echoes the answer
  local prompt="$1" default="${2-}" reply=""
  if [ -t 0 ]; then
    if [ -n "$default" ]; then printf '  %s [%s]: ' "$prompt" "$default" >&2
    else printf '  %s: ' "$prompt" >&2; fi
    read -r reply
  fi
  printf '%s' "${reply:-$default}"
}

write_config() { # write_config <example-basename> <target-basename>
  local tpl="$SRC/docs/agents/$1" dst="$project/docs/agents/$2"

  if [ -f "$dst" ]; then
    say "  keeping existing docs/agents/$2 (delete it to regenerate)"
    skipped=$((skipped + 1)); return 0
  fi
  [ -f "$tpl" ] || { warn "missing template: $1"; return 1; }

  act "write docs/agents/$2"
  [ "$dry" = yes ] && return 0

  mkdir -p "$(dirname "$dst")"
  # `|` as the sed delimiter, because every one of these can contain a slash.
  sed -e "s|<your-site>|${jira_site:-<your-site>}|g" \
      -e "s|<your-cloud-id>|${jira_cloud:-<your-cloud-id>}|g" \
      -e "s|<owner>/<repo>|${gh_repo:-<owner>/<repo>}|g" \
      -e "s|<absolute path to the vault>|${vault:-<absolute path to the vault>}|g" \
      -e "s|PROJ|${key:-PROJ}|g" \
      "$tpl" > "$dst" || return 1
  changed=$((changed + 1))
}

# `gh` already knows the repo when run inside a checkout with a GitHub remote — offering it as
# the default beats making someone retype what the tool can see.
default_gh_repo() {
  (cd "$project" && gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null) \
    || printf '<owner>/<repo>'
}

say ""
if [ "$do_config" = no ]; then
  say "Config: skipped (--no-config). The skills will not work until docs/agents/*.md exist —"
  say "        copy them from payload/docs/agents/*.example.md and fill them in."
elif [ -f "$project/docs/agents/dispatch.md" ] && [ -f "$project/docs/agents/issue-tracker.md" ]; then
  say "Config: docs/agents/ already configured, left alone"
else
  say "Config -> docs/agents/"

  if [ -z "$tracker" ]; then
    if [ -t 0 ]; then
      say ""
      say "  These skills file work as issues and cite them in every ruling, so they need to"
      say "  know where issues live. Which does this project use?"
      say "    1) Jira            — via the atlassian MCP server        [default]"
      say "    2) GitHub Issues   — via the gh CLI"
      say "    3) Obsidian vault  — markdown notes, one file per issue"
      say "    4) something else  — writes a skeleton for you to fill in"
      case "$(ask 'choice' '1')" in
        2) tracker=github ;;
        3) tracker=obsidian ;;
        4) tracker=other ;;
        *) tracker=jira ;;
      esac
    else
      tracker=jira
      say "  not a terminal — assuming --tracker jira; placeholders stay in place"
    fi
  fi

  # Each tracker needs different answers, so ask only for what its template actually uses.
  if [ "$tracker" != other ]; then
    [ -n "$key" ] || key="$(ask 'Issue key prefix (the PROJ in PROJ-12)' 'PROJ')"
  fi
  case "$tracker" in
    jira)
      [ -n "$jira_site" ]  || jira_site="$(ask 'Jira site (the <name> in <name>.atlassian.net)' '<your-site>')"
      [ -n "$jira_cloud" ] || jira_cloud="$(ask 'Jira cloud id (Enter to fill in later)' '<your-cloud-id>')"
      ;;
    github)
      [ -n "$gh_repo" ] || gh_repo="$(ask 'GitHub repo (owner/repo)' "$(default_gh_repo)")"
      ;;
    obsidian)
      [ -n "$vault" ] || vault="$(ask 'Absolute path to the Obsidian vault' '<absolute path to the vault>')"
      ;;
  esac

  write_config "dispatch.example.md" "dispatch.md"
  write_config "evidence-dispatch.example.md" "evidence-dispatch.md"
  write_config "trackers/$tracker.md" "issue-tracker.md"

  # Only useful against Jira's attachment API; a stray copy elsewhere is just confusing.
  [ "$tracker" = jira ] && install_file "scripts/jira-attach.sh" "scripts/jira-attach.sh"
fi

# --- Summary ------------------------------------------------------------------------------
say ""
say "Installed: $changed file(s); already current: $skipped"
say ""
say "Next:"
say "  1. Read docs/agents/dispatch.md and docs/agents/evidence-dispatch.md and make them true"
say "     of this repo. They are the skills' configuration, not documentation — a wrong one"
say "     sends every agent in the run down the wrong path."
if [ "$tracker" = jira ] && [ "$jira_cloud" = "<your-cloud-id>" ]; then
  say "  2. Fill in the Jira cloud id in docs/agents/issue-tracker.md."
fi
say "  3. Restart Claude Code, then /dispatch or /evidence-dispatch."
say ""
say "Both skills are user-invoked only (disable-model-invocation), so nothing runs on its own."
