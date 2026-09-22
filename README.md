# dispatch-skills

A Claude Code workflow that takes an idea to merged, tested code: a spec of testable outcomes,
tickets in your tracker, then parallel implementation where every task's tests are written
first, proven to fail, and made to pass by a different agent that cannot edit them. The tracker
is updated as agents work, so progress is visible there.

```
/setup-workflow          →  config + tracker agent     once per machine: connection, metadata, status line
/spec [grill] <idea>     →  .work/specs/…md            outcomes: Given/When/Then, each testable
/tickets <spec>          →  epic + tasks in tracker    outcome-sliced, blocking edges, waves
/batch-implement <epic>  →  epic branch + draft PR     tests designed, then code, in parallel
```

Every skill is user-invoked only (`disable-model-invocation`), so nothing starts on its own.

> **Status: new, and not yet run end to end.** Each gate script is behavior-tested and the
> installer is tested per tracker, but no epic has yet gone all the way through
> `/batch-implement`. Try it on a small epic first. What is unverified is listed
> [below](#not-yet-verified).

## How a run works

`/batch-implement` orchestrates four agents and writes no product code itself:

| Agent | Tools | Does |
|---|---|---|
| `tracker` | the tracker's only | Every ticket read and write. Moves tasks To Do → In Progress → Done, with an evidence comment at each step |
| `task-planner` | read-only | Before wave 1: waves, file conflicts, interface mismatches, gaps |
| `test-designer` | its own worktree | Writes the task's failing tests and stubs, commits them red |
| `code-writer` | its own worktree | Cherry-picks that red commit, makes the tests pass, cannot change them |

Each wave of unblocked tasks runs in parallel. A task merges into the epic branch only when:

- `verify-red.sh` shows its tests failing at the test-only commit, on an assertion rather than
  an import error;
- the code-writer's commits changed no test file, and `weakened-tests.sh` finds no added skip,
  xfail or TODO and no deleted test;
- the full suite and lint pass on the epic branch after the merge.

There is no per-task code review. The tests are the contract, which is why they are written by
a different agent from the one satisfying them, and proven to fail before any code exists.
Outcomes that need a shared resource (a GPU machine, a device) run one task at a time, after
merge.

## Install

```bash
cd my-project
npx github:assafcaf/dispatch-skills
# or
uvx --from git+https://github.com/assafcaf/dispatch-skills dispatch-skills
```

It installs the skills and agents, then asks where your tickets live:

```
1) Jira            — via the atlassian MCP server        [default]
2) GitHub Issues   — via the gh CLI
3) local files     — markdown under .work/tickets/, not committed
```

Every question has a flag, so an unattended install answers them up front:

```bash
npx github:assafcaf/dispatch-skills --tracker jira --key ENG --jira-site acme
npx github:assafcaf/dispatch-skills --tracker github --gh-repo acme/widgets
npx github:assafcaf/dispatch-skills --tracker local
```

`--dry-run` shows every action without taking one. Re-running is safe: identical files are
skipped, and files that are yours once written are never overwritten.

Then restart Claude Code and run **`/setup-workflow`**. It checks the tracker connection,
discovers what the installer can't (statuses, transition ids, how tasks attach to epics), runs
the config's commands, installs the status line, and offers a short section for your
`CLAUDE.md`.

## What lands where

```
.claude/skills/{spec,tickets,batch-implement,setup-workflow}/
.claude/agents/{tracker,task-planner,test-designer,code-writer}.md
.claude/workflow/config.md              ← yours: tracker, commands, paths, models, resources
.claude/workflow/definition-of-done.md
.claude/workflow/ticket-template.md
.claude/workflow/testing.md             how outcome tests are written
.claude/workflow/trackers/{jira,github,local}.md
.claude/workflow/bin/{verify-red,weakened-tests,vitest-gate}.sh
.claude/workflow/claude-md-snippet.md   offered to your CLAUDE.md by /setup-workflow
.claude/statusline.py                   model, branch, context, cost, live run progress
.claude/settings.json                   ← yours: worktree.baseRef + permissions (never overwritten)
docs/decisions/README.md                ← yours: the committed development record
.gitignore                              + .work/ .claude/worktrees/ CLAUDE.local.md .claude/settings.local.json
```

`.claude/workflow/config.md` is configuration, not documentation. Its **Commands** section is
what every gate runs; it ships with pytest's defaults, and `/setup-workflow` detects your
actual stack and makes it true of your repo — including a gate wrapper where the runner needs
one, `bin/vitest-gate.sh` is a worked example (see `config.example.md`'s Commands section for
why).

Working specs, plans and run logs live in gitignored `.work/`. Decisions a future reader would
otherwise reverse-engineer go in `docs/decisions/`. Facts true of one machine go in a
gitignored `CLAUDE.local.md`, which `/setup-workflow` writes.

## Settings it needs

`worktree.baseRef: head` is required. Without it, implementer worktrees branch from your
default branch instead of the epic branch and miss every earlier task. The shipped
`settings.json` also allows the git commands a run uses unattended, and denies branch
switching, stash, `reset --hard`, force-push and pushes to `main`/`master`. If you already have
a settings file, the installer leaves it alone and `/setup-workflow` merges these in with your
approval.

## Not yet verified

- An epic run end to end through `/batch-implement`.
- That an isolated subagent's worktree branches from the orchestrating session's worktree HEAD
  (the Claude Code docs say it does; untested here).
- That the `tracker` subagent can use the parent session's MCP tools (the docs say `tools:`
  accepts `mcp__<server>`; if not, `tracker` reports it and a run stops rather than letting
  the tracker drift from the code).
- The GitHub and local adapters.

## Upgrading from 0.1

0.1 shipped `/dispatch`, `/evidence-dispatch` and four of Matt Pocock's skills, configured
through `docs/agents/*.md`. 0.2 replaces them. The installer does not remove the old files:
delete `.claude/skills/{dispatch,evidence-dispatch,implement,tdd,review-standards-spec,resolving-merge-conflicts}/`,
`scripts/checks/` and `docs/agents/` if nothing else uses them. 0.1 is still installable from
its last commit: `npx github:assafcaf/dispatch-skills#ccdd421`.

## Licence

MIT — see [LICENSE](LICENSE). Third-party attribution is in [NOTICE](NOTICE).

### A Windows note

Git Bash rewrites POSIX-looking arguments into Windows paths before a native program sees them,
so `--project /home/me/app` reaches `node` already mangled. From Git Bash, pass a Windows-style
path (`--project D:/code/app`) or prefix the command with `MSYS_NO_PATHCONV=1`. From
PowerShell, cmd, macOS or Linux there is nothing to do.
