# 0003 — PAD 0.4.0: ownership units, one owner per ticket, scripts keep the ledger

Applies when: `.claude/workflow/config.md` records a `PAD version:` older than `0.4.0`.

## Steps

The files are already updated: `owner` replaced `ticket-owner` and `code-writer`, and
`epic-merger`, `gate-runner` and `.claude/workflows/pad-task.js` are gone. These are the changes
copying files cannot make.

1. **Agent memory.** If `.claude/agent-memory/ticket-owner/MEMORY.md` or
   `.claude/agent-memory/code-writer/MEMORY.md` exists, append their lines to
   `.claude/agent-memory/owner/MEMORY.md` (create it), drop exact duplicates, and delete the two
   old folders. Lessons about relaying between agents no longer apply: drop those too.
2. **Config.** In `.claude/workflow/config.md`: replace the Agents table's `ticket-owner` and
   `code-writer` rows with `config.example.md`'s `owner` row, keeping the model the
   `code-writer` row had; replace the `### Tiers` subsection with `config.example.md`'s; delete
   Execution's `Mode` line; add the Git moves row `rebase-onto-epic-head` in the form the
   `rebase-red` row has. Then run `/setup-workflow upgrade`, which records `PAD version: 0.4.0`
   and adds any section still missing.
3. **Jira status writes.** With the `jira` adapter, `bin/ledger.sh` moves statuses through the
   Jira REST API. Each operator creates `.work/secrets/jira.env` in the main checkout with
   `JIRA_EMAIL=` and `JIRA_API_TOKEN=` lines (`.claude/workflow/trackers/jira.md`). Say so in
   the pull request; never create the file or ask for the token.
4. **An open epic.** A run started before this update is finished on the old harness, or
   restarted: its owners and code-writers are gone, so `/batch-implement` restarts every
   ticket not yet merged.

## Check

`bash .claude/workflow/bin/preflight.sh` prints `PREFLIGHT OK`, and
`ls .claude/agents/ticket-owner.md .claude/agents/code-writer.md` finds neither.
