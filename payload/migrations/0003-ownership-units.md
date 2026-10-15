# 0003 — PAD 0.4.0: ownership units, one owner per ticket, scripts keep the ledger

Applies when: `.claude/workflow/config.md` records a `PAD version:` older than `0.4.0`.

## Steps

The files are already updated: `owner` replaced `ticket-owner` and `code-writer`;
`task-planner`, `epic-merger`, `gate-runner` and `.claude/workflows/pad-task.js` are gone; tiers
gave way to protected paths; a new `evaluator` agent judges visual tickets; and the
orchestrator skill is now `/pad-run`. These are the changes copying files cannot make.

1. **The skill rename.** `/batch-implement` is now `/pad-run`. `.claude/skills/batch-implement/`
   stays for this version only, as an alias that points to `/pad-run`, and is removed in the
   next. Replace `/batch-implement` with `/pad-run` in the project's own files that name it
   (`CLAUDE.md`'s workflow lines, a project rule, a plugin's `Extends`, a runbook), and say so
   in the pull request.

2. **Agent memory.** If `.claude/agent-memory/ticket-owner/MEMORY.md` or
   `.claude/agent-memory/code-writer/MEMORY.md` exists, append their lines to
   `.claude/agent-memory/owner/MEMORY.md` (create it), drop exact duplicates, and delete the two
   old folders. Lessons about relaying between agents no longer apply: drop those too.
   `.claude/agent-memory/task-planner/` and `epic-merger/`, if present, are deleted the same
   way after moving any lesson that still holds to `owner`. The new `evaluator` keeps no
   memory (a fresh context is its point): create no folder for it.
3. **Config.** In `.claude/workflow/config.md`: replace the Agents table's `ticket-owner` and
   `code-writer` rows with `config.example.md`'s `owner` row, keeping the model the
   `code-writer` row had, add the `evaluator` row, and delete the `task-planner` row; delete the `### Tiers` subsection
   and Execution's `Mode` line; add the Git moves row `rebase-onto-epic-head` in the form the
   `rebase-red` row has. Then run `/setup-workflow upgrade`, which records `PAD version: 0.4.0`
   and adds the sections still missing (`## Protected paths` among them).
4. **Protected paths.** Ask the operator which paths have tests as their only oracle (storage,
   sync, auth, migrations, the data model) and list them as globs under `## Protected paths`.
   Leave the section's "None are configured." when they name none.
5. **Surfaces.** The `## Surfaces` table gains three columns at its end: `Reference dir`,
   `Render command` and `Viewport`. Add them to the header and every row. For a surface that
   is not seen as an image (a CLI, a backend), and in a repo with no visual surface, fill each
   with `-`: it has no visual class and nothing changes. For a surface with mocks, ask the
   operator for the three values (`config.example.md` says what each holds), then check the
   render once with `bash .claude/workflow/bin/render-check.sh --surface <name> --route /
   --viewport <WxH> --out <tmp file>`; `preflight.sh` repeats that check on every run.
6. **Review cadence.** Under `## Review`, set `Cadence` to `per-wave` (the new default: a
   review packet after every wave) unless the config already names a cadence the operator
   chose; an older value that is not one of `per-wave`, `after-first-wave`, `end-only` or
   `none` becomes `per-wave`. Tell the operator in the pull request.
7. **Allow rules.** Owners now rebase and every script under `bin/` runs unattended. Name in
   the pull request the rules `.claude/settings.json` lacks from `settings.example.json`'s
   allow list: `Bash(git rebase *)` and one `Bash(bash .claude/workflow/bin/<script>.sh *)`
   per script; `preflight.sh`'s `commands` check lists any still missing.
8. **Jira status writes.** With the `jira` adapter, `bin/ledger.sh` moves statuses through the
   Jira REST API. Each operator creates `.work/secrets/jira.env` in the main checkout with
   `JIRA_EMAIL=` and `JIRA_API_TOKEN=` lines (`.claude/workflow/trackers/jira.md`). Say so in
   the pull request; never create the file or ask for the token.
9. **An open epic.** A run started before this update is finished on the old harness, or
   restarted: its owners and code-writers are gone, so the run restarts every ticket not yet
   merged. Convert its unmerged tickets to the new body (`ticket-template.md`): `## Goal` becomes
   `## Outcome`, `## Files` becomes `## Owns` (shared files that only gain lines go to
   `## Touches`), `## Tier` becomes `## Protected` (`yes` when the files match a protected
   path), `## Blocked by` becomes `## Depends on`, `## Interfaces` is dropped, and
   `## Reference` names the spec outcome ids. Then run `bash .claude/workflow/bin/plan-check.sh
   <ticket dir>` and fix every `OVERLAPS` and `PROTECTED` line it prints.

## Check

`bash .claude/workflow/bin/preflight.sh` prints `PREFLIGHT OK`, and
`ls .claude/agents/ticket-owner.md .claude/agents/code-writer.md` finds neither.
