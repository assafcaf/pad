# 0003 — PAD 0.4.0: ownership units, one owner per ticket, scripts keep the ledger

Applies when: `.claude/workflow/config.md` records a `PAD version:` older than `0.4.0`.

## Steps

The files are already updated: `owner` replaced `ticket-owner` and `code-writer`;
`task-planner`, `epic-merger`, `gate-runner` and `.claude/workflows/pad-task.js` are gone; tiers
gave way to protected paths. These are the changes copying files cannot make.

1. **Agent memory.** If `.claude/agent-memory/ticket-owner/MEMORY.md` or
   `.claude/agent-memory/code-writer/MEMORY.md` exists, append their lines to
   `.claude/agent-memory/owner/MEMORY.md` (create it), drop exact duplicates, and delete the two
   old folders. Lessons about relaying between agents no longer apply: drop those too.
2. **Config.** In `.claude/workflow/config.md`: replace the Agents table's `ticket-owner` and
   `code-writer` rows with `config.example.md`'s `owner` row, keeping the model the
   `code-writer` row had, and delete the `task-planner` row; delete the `### Tiers` subsection
   and Execution's `Mode` line; add the Git moves row `rebase-onto-epic-head` in the form the
   `rebase-red` row has. Then run `/setup-workflow upgrade`, which records `PAD version: 0.4.0`
   and adds the sections still missing (`## Protected paths` among them).
3. **Protected paths.** Ask the operator which paths have tests as their only oracle (storage,
   sync, auth, migrations, the data model) and list them as globs under `## Protected paths`.
   Leave the section's "None are configured." when they name none.
4. **Allow rules.** Owners now rebase and every script under `bin/` runs unattended. Name in
   the pull request the rules `.claude/settings.json` lacks from `settings.example.json`'s
   allow list: `Bash(git rebase *)` and one `Bash(bash .claude/workflow/bin/<script>.sh *)`
   per script; `preflight.sh`'s `commands` check lists any still missing.
5. **Jira status writes.** With the `jira` adapter, `bin/ledger.sh` moves statuses through the
   Jira REST API. Each operator creates `.work/secrets/jira.env` in the main checkout with
   `JIRA_EMAIL=` and `JIRA_API_TOKEN=` lines (`.claude/workflow/trackers/jira.md`). Say so in
   the pull request; never create the file or ask for the token.
6. **An open epic.** A run started before this update is finished on the old harness, or
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
