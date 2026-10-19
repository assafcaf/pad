# dispatch-skills

A Claude Code workflow (PAD) that takes an idea to merged, tested code: a scope that names what
each part is judged against, tickets that are ownership units in your tracker, then a run where
one owner per ticket builds it end to end, in parallel, and scripts land the code and keep the
ledger. The tracker is updated as tickets merge, so progress is visible there.

```
/setup-workflow          →  config + tracker agent     once per machine: connection, metadata, status line
/knowledge-layer         →  CONTEXT.md + project.md    optional: a glossary, and what an agent cannot infer
/spec [grill] <idea>     →  .work/specs/…md            the scope: intent, references, protected paths, domains
/tickets <spec>          →  epic + tickets in tracker  ownership units, linted by plan-check.sh
/pad-run <epic>          →  epic branch + draft PR     one owner per ticket; scripts merge and record
```

Every workflow skill but `/knowledge-layer` is user-invoked only (`disable-model-invocation`), so
nothing starts on its own. `/knowledge-layer` stays callable by an agent because
`/setup-workflow` and `/pad-run` run it; the optional [`writing-for-readers`](#writing-for-readers)
skill is the one Claude starts by itself.
`/batch-implement` is the 0.3 name of `/pad-run`, kept as an alias for one version.

> **Status: 0.4.0, a redesign not yet run end to end.** Each gate script is behaviour-tested
> and the installer is tested per tracker, but no epic has yet gone all the way through
> `/pad-run`. Try it on a small epic first. What is unverified is listed
> [below](#not-yet-verified). Why it changed is in
> [`docs/decisions/0005`](docs/decisions/0005-ownership-units-one-owner-scripts-keep-the-ledger.md).

## How you use it

Three commands and four approval points; between them, the run goes on unattended.

| Step | You run | You approve | Then it runs unattended |
|---|---|---|---|
| 1 | `/spec [grill] <idea>` | the scope | — |
| 2 | `/tickets <spec>` (same session) | the ticket list | publishing the epic and its tickets |
| 3 | `/pad-run <epic>` | the waves and the epic branch, once; then a review packet per wave | every ticket, through to the draft PR |
| 4 | — | the PR: you merge it | cleanup, when you say it has merged |

`/setup-workflow` comes before all of it, once per machine. `/knowledge-layer` is optional and
can be run at any point; see [below](#the-knowledge-layer).

**1. Idea → scope.** `/spec <idea>` brainstorms: purpose and constraints, then two or three
approaches with trade-offs, then the design in short sections you confirm one at a time.
`/spec grill <idea>` is the adversarial version. It maps the idea as a tree of decisions and
walks it depth-first, asking the hardest question each one raises, pushing back on "fast",
"robust" and "handle errors" until each is a number, a behaviour or a non-goal. Grill when you
know roughly what you want and need the holes found; brainstorm when you don't know yet.

The scope names, for every area, the **reference** the result is judged against: a mock crop
at a viewport, outcomes a test can check, a failing repro, a baseline file. An area with no
reference gets a spike first. It lists the **protected paths** (storage, sync, auth,
migrations, the data model: where tests are the only oracle) and the domains, as bullets, not
tasks. Outcomes in "Given …, when …, then …" form are written only where tests are the
reference. Decisions a future reader would otherwise reverse-engineer go to
`docs/decisions/NNNN-<slug>.md`, committed.

**2. Scope → ownership units.** `/tickets <spec>` cuts the work into tickets one owner can take
from start to merged. Each ticket **owns** a set of files no other ticket writes, may only
**add** to shared files (a registry, a router), names its **reference**, and fits one agent's
session. It splits by surface or module, never by concern: "all colours" or "every button"
touches every file and collides with everything. A cross-cutting concern is a line in the run's
brief, or a foundation ticket that lands first. `plan-check.sh` lints the list before you see
it: overlapping files, a protected path not marked protected, a dependency cycle, hot shared
files, sweeps. **Nothing is published before you approve it.** Then it publishes through
`tracker`, which refuses to create a duplicate, so a half-finished run can be re-run.

**3. Tickets → merged code.** `/pad-run <epic key>` creates the epic branch, writes a short
brief every owner reads (links to the scope, the references, the code's existing system, the
gates, who owns what), and dispatches one `owner` per ready ticket. Each owner reads the
reference itself, builds, proves its tests fail before the code and pass after, gates, rebases
onto the epic head and reports one line. The orchestrator lands each `READY` with
`merge-task.sh` in the background, and that script writes the evidence, the run log, the ticket
status and the board. After each wave you get a review packet (`review.sh`): what merged, the
render pairs side by side, what nobody verified. Your feedback becomes new tickets. The run
stops only for an irreversible or security-sensitive action, a change to shared state outside
the epic branch, a red baseline, or a change of scope.

**4. What you get back.** The epic branch pushed, and a draft PR whose body carries the ticket
table, every ruling, failed tickets, test removals with the rule that explains each, the run's
measured stats, and what was not verified. You merge it; then `/pad-run` runs
`cleanup-run.sh`, which removes the run's worktrees, branches, locks and run files, so nothing
piles up.

## How a run works

```
orchestrator (/pad-run)            partition · sequence · land · replan · escalate
├── E3-T4-owner   (owner)          one per ticket, its own worktree, start to merged
│   ├── E3-T4-tests  (test-designer)   only for a protected ticket, as a blocking child
│   └── E3-T4-eval   (evaluator)       only for a visual ticket: fresh-context verdict
├── E3-T7-owner   (owner)          talks to E3-T4-owner directly, or through channel.md
└── scripts: plan-check · merge-task · ledger · review · run-stats · cleanup-run
```

| Agent | Does |
|---|---|
| `owner` | One ticket from start to merged: reads the reference, writes the code (and the tests unless protected), proves red, gates, rebases, reports one line. Talks to other owners directly |
| `test-designer` | A protected ticket's failing tests and stubs, committed red; the owner may not change them |
| `evaluator` | Judges a visual ticket's render against its mock crop with a fresh context. The owner's own eye never closes a visual ticket |
| `tracker` | Tracker reads, creates and links. Status writes go through `ledger.sh` |
| `memory-curator` | Once, at the end of the epic: keeps the agents' lessons accurate and short, never adds one |

**One writer per ticket, parallelism only across tickets.** Two writers inside one task, and
tickets cut by concern, are what produced conflicts and drift in 0.3. **Ceremony follows what
the diff touches**: a diff on a protected path needs a red commit a test-designer wrote, and
`merge-task.sh` rejects it otherwise; everywhere else the owner chooses its tests. **The
orchestrator pays per hand-off**, so a ticket costs it one dispatch and one background merge,
and every piece of bookkeeping is a script.

A ticket merges into the epic branch only when:

- its reference holds, judged by someone other than its writer: tests proven red at a
  test-only commit (`verify-red.sh`) and green after, or an `evaluator` verdict on a render;
- `task-submit.sh` finds no change outside the ticket's files, and `weakened-tests.sh` finds no
  added skip, xfail or TODO and no removed test a rule doesn't explain;
- the full suite, typecheck and lint pass on the epic branch after the merge, one merge at a
  time, so a red is always one ticket's.

The run's state is in files (`.work/runs/<epic>/`: `scope.md`, `brief.md`, `board.md`,
`channel.md`) and git, so a killed run resumes: a new orchestrator reads them and continues, and
a new owner picks up an open ticket from its branch. Outcomes that need a shared resource (a GPU
machine, a device) run one ticket at a time, after merge.

## Install

```bash
cd my-project
npx github:assafcaf/dispatch-skills
# or
uvx --from git+https://github.com/assafcaf/dispatch-skills dispatch-skills
```

It asks whether to include the optional `writing-for-readers` skill (default yes), installs the
skills and agents, then asks where your tickets live:

```
1) Jira            — via the atlassian MCP server        [default]
2) GitHub Issues   — via the gh CLI
3) local files     — markdown under .work/tickets/, not committed
```

Every question has a flag, so an unattended install answers them up front:

```bash
npx github:assafcaf/dispatch-skills --tracker jira --key ENG --jira-site acme
npx github:assafcaf/dispatch-skills --tracker github --gh-repo acme/widgets
npx github:assafcaf/dispatch-skills --tracker local --no-writing-skill
```

### writing-for-readers

An optional skill that Claude invokes on its own whenever it writes prose for a person: a
document, a README, a report or summary in the chat, a PR body. It puts the point first, keeps
each section within a reader's working memory, and shows processes, comparisons and formulas
as diagrams, tables and equations instead of narrating them. `--writing-skill` and
`--no-writing-skill` answer the installer's question; without a terminal it is installed.
Declining installs nothing, and `/pad-update` then leaves it out too. To add it later, re-run
the installer with `--writing-skill`.

`--dry-run` shows every action without taking one. Re-running is safe: identical files are
skipped, and files that are yours once written are never overwritten.

Then restart Claude Code and run **`/setup-workflow`**. It checks the tracker connection,
discovers what the installer can't (statuses, transition ids, how tasks attach to epics), runs
the config's commands, installs the status line, asks whether you want the knowledge layer, and offers a short
section for your `CLAUDE.md`.

## Updating

PAD keeps changing. In an installed project, run **`/pad-update`** to bring the harness up to
PAD's latest commit (or `/pad-update <ref>` for a named one). It clones PAD, and on a branch:

- updates every file PAD ships, with a three-way merge against the PAD commit the project was
  installed from (`.claude/workflow/pad.lock`): untouched files are replaced, files only the
  project changed are kept, files both changed are merged, and you are asked only about a real
  conflict;
- deletes files PAD retired, unless the project changed them;
- runs the migration notes in `payload/migrations/` the project has not handled yet: the
  changes copying files cannot make;
- brings `config.md` up to the new version, runs preflight and the rehearsal, and opens a pull
  request that lists what changed and what is left for you (permission rules are never written
  for you).

A project installed before `/pad-update` existed has no lock and no such skill. Get the skill
by re-running the installer once, or by copying `payload/claude/skills/pad-update/` into
`.claude/skills/`; the first run finds the commit the harness came from by comparing files and
asks you to confirm it.

When a push to PAD needs more than file copies in the projects that use it, add a note:
`payload/migrations/README.md` has the format.

## What lands where

```
.claude/skills/{spec,tickets,pad-run,batch-implement,setup-workflow,knowledge-layer,pad-update}/
.claude/skills/writing-for-readers/     optional; the one skill Claude invokes on its own
.claude/workflow/pad.lock               the PAD commit the harness came from; committed
.claude/agents/{owner,test-designer,evaluator,tracker,memory-curator,knowledge-scanner}.md
.claude/agent-memory/<agent>/MEMORY.md  each agent's lessons, committed; created as agents learn
.claude/workflow/config.md              ← yours: tracker, commands, paths, models, resources
.claude/workflow/definition-of-done.md
.claude/workflow/ticket-template.md
.claude/workflow/brief-template.md      the run brief every owner reads
.claude/workflow/testing.md             how outcome tests are written
.claude/workflow/writing-files.md       which tool writes a prose file, and why not a heredoc
.claude/workflow/agent-memory.md        what an agent may write to its memory, and how
.claude/workflow/trackers/{jira,github,local}.md
.claude/workflow/bin/*.sh               the gates and the bookkeeping: merge-task, ledger, plan-check, review, ...
.claude/workflow/rules/                 rules agents load at start; add your own beside them
.claude/workflow/claude-md-snippet.md   offered to your CLAUDE.md by /setup-workflow
.claude/statusline.py                   model, session address (@name), branch, context, cost, progress
.claude/settings.json                   ← yours: worktree.baseRef + permissions (never overwritten)
docs/decisions/README.md                ← yours: the committed development record
CONTEXT.md                              ← yours: the glossary, if the layer is on
.claude/workflow/project.md             ← yours: the notes agents cannot infer, if it is on
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

## Agent memory

The agents a run uses — `owner`, `test-designer` and `tracker` — each keep a memory (`memory: project`), which Claude Code loads every time the agent
starts. An agent writes a line only after something failed or blocked it, it found what works,
and its next run would hit the same wall: one line, with the task key and date
(`.claude/workflow/agent-memory.md`). A denied command, a tool limit, a gate that fails for a
non-obvious reason — each is learned once.

A memory written by the model it guides can drift into noise, and agents follow bad guidance
rather than ignoring it. So at the end of each epic, `memory-curator` checks every line: still
true, not a one-task fact, not said elsewhere, short. It deletes, tightens, merges or moves
lines, never adds any, and commits the result on the epic branch. Its changes are listed in the
PR, along with anything it found that belongs in `project.md` (the operator's to write) or that
is really a harness bug to fix upstream.

This is separate from the knowledge layer below. Memory is what an agent learned about doing
its job here; `project.md` is what the operator knows about the product.

## The knowledge layer

Optional, and off unless you turn it on. `/knowledge-layer` writes two files:

| File | Carries |
|---|---|
| `CONTEXT.md` | the glossary: one word per concept, and the synonyms it beats |
| `.claude/workflow/project.md` | module map, invariants, standing overlaps, pitfalls |

It is built in two halves, because only one half is safe to generate. Read-only
`knowledge-scanner` agents fan out over the repo and report what carries a path: modules,
declared commands, term candidates, and the files recent commits keep touching. Everything that
cannot be cited (what the repo is for, what must stay true, what newcomers get wrong) is asked
of you and written down in your words.

That split is not caution for its own sake. A repository context file written by a model
measured **worse than no file at all** ([arXiv 2602.11988][ctx]: -0.5% on SWE-bench Lite, -2%
on AGENTbench, and over 20% added inference cost per task); one written by the repo's own
developers measured **+4%**. Agents obey a wrong context file rather than ignoring it.

`bash .claude/workflow/bin/knowledge-paths.sh` fails when a path either file names has gone, or
when either grows past its ceiling. `/pad-run` ends an epic by naming what the layer was
missing, which is the half with evidence behind it: guidance tuned against observed agent
failures beats one-shot generation ([arXiv 2606.20512][pr]).

Turn it on at any time with `/knowledge-layer`, re-scan with `/knowledge-layer refresh`, and
turn it off by setting `Mode: off` in the config. With it off every skill and agent behaves
exactly as it did before the layer existed.

[ctx]: https://arxiv.org/abs/2602.11988
[pr]: https://arxiv.org/abs/2606.20512

## Settings it needs

`worktree.baseRef: head` is required. Without it, implementer worktrees branch from your
default branch instead of the epic branch and miss every earlier merge. The shipped
`settings.json` also allows the git commands a run uses unattended, and denies branch
switching, stash, `reset --hard`, force-push and pushes to `main`/`master`. If you already have
a settings file, the installer leaves it alone and `/setup-workflow` merges these in with your
approval.

## Not yet verified

- An epic run end to end through `/pad-run`, and the measured comparison with 0.3 that
  decision 0005 calls for: turns per ticket, conflicts, rework rounds, operator interventions.
- That the permission classifier lets an owner rebase and resubmit unattended.
- The `evaluator`'s verdicts against real mocks, and `render-check.sh` with a real renderer.
- The Jira and GitHub status writes in `ledger.sh` against a live tracker (both are tested
  against stubs).
- That an isolated subagent's worktree branches from the orchestrating session's worktree HEAD
  (the Claude Code docs say it does; untested here).
- That the `tracker` subagent can use the parent session's MCP tools (the docs say `tools:`
  accepts `mcp__<server>`; if not, `tracker` reports it and a run stops rather than letting
  the tracker drift from the code).
- The GitHub and local adapters.
- Agent memory in a real run: that memory stays in the main checkout for worktree-isolated
  agents (the docs say so), and that `memory-curator` keeps it useful.
- `/knowledge-layer` end to end on a real repo. Its gate script is exercised against
  passing, missing-path, over-ceiling and mode-off cases; the scan-and-grill flow is not.

## Licence

MIT — see [LICENSE](LICENSE). Third-party attribution is in [NOTICE](NOTICE).

### A Windows note

Git Bash rewrites POSIX-looking arguments into Windows paths before a native program sees them,
so `--project /home/me/app` reaches `node` already mangled. From Git Bash, pass a Windows-style
path (`--project D:/code/app`) or prefix the command with `MSYS_NO_PATHCONV=1`. From
PowerShell, cmd, macOS or Linux there is nothing to do.
