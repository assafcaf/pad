---
name: setup-workflow
description: Wire this repo's delivery workflow to a machine and a tracker - detect the environment, verify the tracker connection, write the config and the tracker agent, and check the harness is sound. Run once per machine, and again when the tracker or the toolchain changes.
argument-hint: "[jira | github | local]"
disable-model-invocation: true
---

# Set up the workflow here

Input: `$ARGUMENTS` names the tracker adapter; ask if it's missing. Nothing in this skill
creates a ticket or changes product code. Report findings as a checklist: what is ready, what
you fixed, what the operator must do.

## 1. The machine

Detect rather than assume; this repo is worked on from more than one kind of machine. Run the
checks, then write what you found to `CLAUDE.local.md` (gitignored, loaded into every session
in this checkout — never commit it).

| Check | How |
|---|---|
| OS and shell | `uname -s -r` (or `$OS`), and which shell this session runs |
| Toolchain | `git --version`, `gh --version`, and the versions of whatever the config's commands call |
| Suite | the configured setup and full-suite commands: record the pass/skip counts and the runtime here |
| Serial resources | for each one in the config, does its runner reach it from here? |
| Tracker CLI | `gh auth status` when the adapter is `github` |

Write only facts that differ between machines, in this shape:

```markdown
# Local environment (not committed)

Observed <yyyy-mm-dd> by /setup-workflow.

- OS / shell: <…>
- Suite here: `<command>` → <n> passed, <m> skipped, ~<t>s
- <platform quirks that cost someone an hour here, e.g. path or shell differences>
- Serial resources: <tag: reachable / unreachable>
```

Anything true on every machine belongs in `CLAUDE.md` or a skill instead, not here.

## 2. The tracker

**`jira`:**
1. **Connection.** Call `atlassianUserInfo`. If the tools are missing or unauthorized, stop
   and tell the operator to run `/mcp`, pick `atlassian` and authenticate — the OAuth consent
   opens in a browser, so only they can do it. `.mcp.json` is read at session start, so a
   server added now needs a restart.
2. **Discover, never guess:** `getVisibleJiraProjects` for the cloud id and project (ask which
   project if more than one), `getJiraProjectIssueTypesMetadata` for the epic and task type
   names, `getIssueLinkTypes` for the blocking link, and `getTransitionsForJiraIssue` on any
   existing issue for the status names and transition ids.
3. **How tasks attach to epics.** Read one existing task that has an epic. If its `parent` is
   the epic, the project is team-managed and `createJiraIssue` takes `parent: <EPIC>`. If the
   epic sits in a custom field (usually "Epic Link"), note that field id in the config and in
   the adapter's Create task row.
4. **Record** all of it in `.claude/workflow/config.md`'s Tracker section, transition ids
   included.

**`github`:** confirm `gh auth status` and that the repo has issues enabled. **`local`:** no
connection to check.

Then write `.claude/agents/tracker.md` from
`.claude/skills/setup-workflow/tracker-agent-template.md`: fill in the adapter name and the
tools it needs (`mcp__atlassian` for Jira, `Bash` for GitHub, `Read, Edit, Write` for local).
Everything else the agent reads from the config at run time.

## 3. The status line

`.claude/statusline.py` is committed; where it lives on this machine is not. Install it into
`.claude/settings.local.json` (gitignored), merging with whatever that file already holds
rather than overwriting it:

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 /absolute/path/to/repo/.claude/statusline.py"
  }
}
```

- Use whichever Python 3 this machine has: `python3`, `python`, `py -3`, or
  `uv run --no-project python`. Check it runs before writing it in.
- Write the checkout's **absolute path with forward slashes**, even on Windows: Git Bash eats
  backslashes in this field and the status line then fails silently.
- If the operator already has a `statusLine` in their user settings, say what this one adds
  (the run progress of `/batch-implement`) and ask before shadowing it for this project.
- Test it before reporting success:
  `echo '{"model":{"display_name":"test"}}' | python3 .claude/statusline.py`
  should print one line. It takes effect in the next session.

## 4. The harness

Check, fix what you safely can, and report the rest:

- `.claude/settings.json` sets `worktree.baseRef` to `head` — required for parallel waves. If
  the installer found an existing settings file it left it alone and wrote
  `.claude/settings.example.json`; merge its `worktree` key and permission rules in,
  preserving everything already there, and show the operator the diff.
- `.gitignore` covers `.work/`, `.claude/worktrees/`, `CLAUDE.local.md` and
  `.claude/settings.local.json`.
- `.claude/workflow/bin/*.sh` are executable (`git ls-files -s`, mode `100755`).
- The config's commands all run here: setup, full suite, lint. Quote the results.
- Serial resources in the config are reachable, or say which are not.
- The permission rules still cover what `/batch-implement` runs unattended: `git worktree add`
  and `remove`, `add`, `commit`, `cherry-pick`, `merge`, `revert`, `rev-parse`, `fetch`,
  `push origin`, and `gh pr create`; with pushes to the default branch denied. Report anything
  missing rather than adding it — widening permissions is the operator's to approve.

## 5. CLAUDE.md

Offer the sections in `.claude/workflow/claude-md-snippet.md` — how work flows here, and the
writing rules — for the repo's `CLAUDE.md`. Show them, add only what the operator accepts, and
keep each addition short: every line of `CLAUDE.md` loads into every session.

## 6. Report

One checklist. For anything unresolved, name the command the operator should run. Finish with
the flow they can now use: `/spec` → `/tickets` → `/batch-implement`.
