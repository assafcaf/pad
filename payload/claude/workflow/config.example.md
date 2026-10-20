# Workflow config

Read by `/spec`, `/tickets`, `/pad-run` and the agents in `.claude/agents/`. Everything
specific to this repository lives here, so the skills and agents stay project-agnostic. The
installer wrote this from your answers; `/setup-workflow` fills in what it can discover
(statuses, transition ids, the commands that actually run here) and checks the rest. After
that it is yours: edit it when the project changes.

PAD version: <PAD_VERSION>

<!-- Section manifest: the `## ` headings below are the sections a config of this PAD version
has. `bin/preflight.sh` fails when config.md lacks one, or records an older PAD version, and
names `/setup-workflow upgrade`. -->

## Tracker

- **Adapter:** `<TRACKER>`. Operations are in `.claude/workflow/trackers/<TRACKER>.md`; the
  alternatives are `jira`, `github` and `local`.
- **Jira:** site `https://<JIRA_SITE>.atlassian.net`, cloudId `<JIRA_CLOUD_ID>`, project
  `<KEY>`.
- **GitHub:** repository `<GH_REPO>`.
- **Issue types:** epic `Epic`, task `Task`, bug `Bug`.
- **Statuses:** todo `To Do`, doing `In Progress`, review `In Review`, done `Done`. Transition
  ids: filled in by `/setup-workflow`. A task that passes the definition of done moves to done;
  the epic moves to review when its PR opens.
- **Blocking link:** `Blocks`.
- **Label for agent-created tickets:** `agent-planned`.

Delete the lines for trackers you don't use.

## Agents

Roles are agents in `.claude/agents/`, so each carries its own tools. Change a model here, not
in the agent file.

| Role | Agent | Model | Notes |
|---|---|---|---|
| Tracker | `tracker` | `haiku` | The only agent with tracker tools: reads, creates, links. Status writes go through `bin/ledger.sh` |
| Ownership | `owner` | `sonnet` | One per ticket, its own worktree, start to merged: writes the code (and the tests unless protected), proves red, gates, rebases, reports one line |
| Tests | `test-designer` | `sonnet` | Its own worktree, a blocking child of an owner whose ticket is protected. Writes the failing tests and stubs |
| Visual judge | `evaluator` | `sonnet` | Fresh context, dispatched by an owner on a visual ticket: compares the render with the reference and returns a verdict. Never sees the owner's reasoning |
| Knowledge scan | `knowledge-scanner` | `sonnet` | Read-only. Several at once, and only during `/knowledge-layer` |
| Memory curation | `memory-curator` | `sonnet` | Once per epic, at the end. Keeps the agents' memory clean; never adds a lesson |

**Thinking effort** is set in an agent file's `effort:` field, and a dispatch can't override it.
The agents inherit the session's effort.

**Memory.** `owner`, `test-designer` and `tracker` have `memory: project`: each keeps lessons
in `.claude/agent-memory/<agent>/MEMORY.md`, committed and loaded on every start. The rules
are in `.claude/workflow/agent-memory.md`, and `memory-curator` enforces them at the end of
each epic.

## Protected paths

Where tests are the only oracle — storage, sync, auth, migrations, the data model — a diff
takes the strict discipline: a `test-designer` writes the tests as the owner's blocking child,
red is proven, and the tests are read-only to the owner. Everywhere else the owner writes its
own tests, or none for a visual reference. One glob per line; `/tickets` marks every ticket
that matches one `Protected: yes`, `plan-check.sh` fails a ticket that matches but says no, and
`merge-task.sh --protected` rejects a protected diff whose red commit no test-designer wrote.
None are configured.

<!-- - `src/db/**` -->

## Tracker updates during a run

So progress is visible without reading the terminal. Scripts write all of these
(`bin/ledger.sh`, called by the orchestrator at dispatch and by `merge-task.sh --run` at merge);
with `jira` they need `.work/secrets/jira.env` (`trackers/jira.md`, "Status writes from
scripts"):

| When | Task | Comment |
|---|---|---|
| Wave starts | → doing | run id and epic branch |
| Merged and gates green | → done | at most five lines: merge and red shas, red and green commands with results, files outside the ticket's list. The full evidence is in `.work/runs/<run id>/<KEY>.md` |
| Gate failed or blocked | stays doing | what failed, and what is needed |
| Epic finished | epic → review | PR URL |

## Plugins

Project-owned additions to PAD's agents and skills (`.claude/workflow/plugins.md`). Each file is
under `.claude/pad-plugins/`, which `/pad-update` never touches; only the plugins listed here
are in force.

| Plugin | Extends | Adds |
|---|---|---|

None installed.

## Paths

| What | Where | Committed |
|---|---|---|
| Working specs | `.work/specs/<yyyy-mm-dd>-<slug>.md` | no |
| Plans (task bodies + tracker keys) | `.work/plans/<slug>.md` | no |
| A run's files: scope, brief, board, channel, run log, ticket bodies, evidence, review packets | `.work/runs/<run-id>/{scope,brief,board,channel,progress}.md`, `tickets/`, `evidence/<KEY>/`, `review-<n>.md` | no |
| Jira credentials for `ledger.sh` | `.work/secrets/jira.env` | no |
| Progress snapshot for the status line | `.work/progress.json` | no |
| Development record | `docs/decisions/NNNN-<slug>.md` | yes |
| Promoted specs | `docs/specs/<slug>.md` | yes, only when the operator says so |

`spec_commit: ask`. After a spec is approved, ask once whether to promote it. Default: no.

## Project knowledge

Mode: off

Off is what every skill and agent did before the knowledge layer existed, so leaving it off
changes nothing. Run `/knowledge-layer` to turn it on: it scans the repo for what it can cite,
asks you for what it cannot, writes `CONTEXT.md` and `.claude/workflow/project.md`, and
replaces this paragraph with the table of what each reader reads. Until then, agents work from
`CLAUDE.md` as they always have.

A repo of several packages gets a `Packages:` line here (backtick paths, or a glob such as
`packages/*/`) and one knowledge level per package beside its code; see the skill.

## Commands

Replace these with the commands that work in this repo; `/setup-workflow` runs each one and
reports what fails. The defaults below are pytest's, because they're the easiest stack to show
the contract on — not because the workflow assumes Python. `/setup-workflow`'s stack step
detects the real runner and fills this table in.

| Gate | Command |
|---|---|
| Setup in a fresh worktree | `pip install -e .` |
| Run named tests | `python -m pytest -q {tests}` (`{tests}` = space-separated node ids) |
| Full suite | `python -m pytest -q` |
| Typecheck | `true` (none configured) |
| Lint | `true` (none configured) |
| Dependency directory | none (e.g. `node_modules`; `verify-red.sh --deps` links it instead of running setup) |
| Lockfile | none (e.g. `package-lock.json`; setup runs again only when it changes from the base) |
| Red means | exit code `1`: tests collected, ran, and failed. Collection errors (exit `2`) do not count |
| Test paths | `tests/` |
| Dev tests | `tests/_dev/` — where owners keep development tests, never committed (`.claude/workflow/testing.md`, "Permanent and development tests") |
| Derived files | none (e.g. `README.md: python scripts/readme_counts.py`; `uv.lock: uv lock`). One `<path>: <command>` per file every task may change that is rebuilt, not merged: `merge-task.sh --derived` takes the epic's copy on a conflict that touches only these files, runs the command on the merged tree and gates the result. Pair a rebuilt lockfile with a check in Lint (`uv lock --check`, `npm ci --dry-run`) so a stale lock fails the gate |
| Weakened tests | `bash .claude/workflow/bin/weakened-tests.sh <base> <head>` (pytest patterns by default; set `WEAK_ADDED` and `TEST_DEF` for another stack — see the script's header) |

**The exit-code contract.** "Red means" exists to tell "the test ran and failed" apart from
"the test never ran" (`definition-of-done.md`, item 2) — without that split, a task whose test
file fails to import certifies as red with no assertion ever executed. pytest gives this for
free: exit `1` is a failed assertion, exit `2` is a collection error, so its row above is just
those two numbers. Most other runners don't: vitest, jest, `go test` and `cargo test` all exit
`1` for both a failing assertion and a file that fails to load. On those, wrap the runner and
remap its output onto pytest's split before filling in this table — `bin/vitest-gate.sh` is a
worked example (0 passed, 1 real failure, 2 nothing ran); adapt its output-matching to the
runner you actually have rather than reusing vitest's wording. `/setup-workflow`'s stack step
checks which case you're in.

## Git moves

The git commands the workflow's agents run, one per capability, each in the form this repo's
settings allow. `bash .claude/workflow/bin/check-moves.sh` proves every row against the
effective settings (`~/.claude/settings.json`, `.claude/settings.json`,
`.claude/settings.local.json`): a command must match an allow rule and no deny rule, since one
that matches neither would stop the run on a prompt. A failing row prints the allow rule to add.
`<sha>`, `<branch>` and `<path>` stand for any value.

| Capability | Command |
|---|---|
| `branch-from-epic-head` | `git switch -c <branch> <sha>` |
| `move-onto-sha` | `git reset --hard <sha>` |
| `take-red` | `git merge --ff-only <sha>` |
| `rebase-red` | `git rebase <sha>` |
| `rebase-onto-epic-head` | `git rebase <sha>` |
| `discard-changes` | `git checkout -- <path>` |
| `set-aside-work` | `git stash push -u` |
| `try-merge` | `git merge --no-ff --no-commit <branch>` |
| `abort-merge` | `git merge --abort` |
| `commit-merge` | `git commit --no-edit` |
| `revert-merge` | `git revert -m 1 <sha>` |
| `push-epic` | `git push origin <branch>` |
| `remove-worktree` | `git worktree remove <path>` |
| `delete-merged-branch` | `git branch -d <branch>` |

## Serial resources

Outcomes tagged with a resource run one task at a time, by the orchestrator, after merge. Use
this for anything the host can't provide or can't share: a GPU machine, a device, a staging
database. None are configured.

Each resource has a class. `automated`: the orchestrator runs the command and reads the result
itself. `operator-run`: only a person can run it (a real session, a device); the orchestrator
does not run it but writes a review packet for the operator, and the outcome waits on that.

| Tag | Class | Meaning | How to run |
|---|---|---|---|
| `<tag>` | `automated` or `operator-run` | `<what needs it>` | `<command that runs a test there, and how to check it's free>` |

## Surfaces

The places where the product is seen or used. Optional; none are configured.

| Surface | Entry point | Test drives it by | Person looks by | Automated check | Preview start | Ready when | Restart when changed | Cannot show | Reference dir | Render command | Viewport |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `<name>` | `<url, command or file>` | `<how a test drives it>` | `<how a person looks>` | `<command>` | `<dev server command>` | `<signal it is up>` | `<paths that need a restart>` | `<what it cannot show>` | `<where the mock crops live>` | `<command writing {out} for {route} at {width}x{height}>` | `<WxH>` |

A surface with a **Render command** has a visual reference class: tickets on it are judged
against a mock crop from its **Reference dir**, at its **Viewport**, by the `evaluator`
(`definition-of-done.md`). `bin/render-check.sh` runs the command with `{route}`, `{viewport}`,
`{width}`, `{height}`, `{state}` and `{out}` filled in, and `preflight.sh` runs it once,
before any preview is started: the command brings up what it renders itself (a test
runner's own web server, a build it serves, a CLI it runs), never a running preview. A
surface without one — a CLI, a backend — has no visual class; nothing in PAD assumes a web app.

## Review

- **Cadence:** `per-wave`. When the operator reviews the running product, from the packet
  `bin/review.sh` writes; feedback becomes new tickets. Options: `per-wave` (after every
  wave), `after-first-wave` (once, after the first wave merges),
  `end-only` (once, before the PR), `none`.

## Execution

- **Branches:** epic branch `epic/<KEY>-<slug>`, in worktree `.claude/worktrees/<KEY>`.
  `.claude/settings.json` must set `worktree.baseRef: head`, so implementer worktrees branch
  from the epic branch.
- **Parallelism:** `none`: every ready task starts at once. Set a number only to cap
  owners; host load is already bounded by suite slots, below.
- **Gate:** `affected`. What `merge-task.sh` runs per merge: `full` (the full suite) or
  `affected` (the named-tests command on the tests the change reaches through imports, from
  `bin/affected-tests.sh`; the full suite still runs when a conftest, manifest, lockfile or
  test helper changed). `affected` is safe as the default because the epic's final full gate
  runs the whole suite on the finished branch before the PR, so anything a selective merge
  gate missed is caught there. `batch` gates with `--gate affected` when this is `affected`.
  `/pad-run --gate` overrides it.
- **Merge strategy:** `dynamic`. How tickets land: `dynamic` lets `/pad-run` choose among the
  strategies (`single`, `batch`, and any of the repo's own) from the run's signals and switch
  as they change; a fixed name (`single`, `batch`, or a strategy of your own) uses only that
  one. Strategies are `<name>.md` + script pairs in `.claude/workflow/merge-strategies/`; a
  repo adds its own with `/merge-strategy`, and `/pad-update` never touches them.
- **Test workers:** `none`. A number caps the workers a parallel suite may start on this host
  (e.g. `-n {workers}` with pytest-xdist): `merge-task.sh --workers` fills `{workers}` in the
  Full suite and Run named tests commands. Size it so a gate plus the agents' named-test runs
  fit in RAM: each worker loads the whole import graph. Run `load-probe.sh` with the
  parallel command three times before adopting it, and give the suite a per-test timeout
  (pytest-timeout's `--timeout=<s>`) so a hung test fails instead of holding a slot.
- **Suite slots:** `2` — at most this many full-suite runs at once, through `bin/suite-slot.sh`;
  a waiting merge gate goes first. `PAD_SUITE_SLOTS` overrides it.
- **Host suite slots:** `none`. A number caps full-suite runs across every repo on this host
  (read by `bin/suite-slot.sh`; slots live under `PAD_HOST_SLOTS_DIR`, else `~/.pad/slots`).
- **Final review:** `off`. Set to a `/code-review` level (`low`, `medium`, …) to run one
  review over the finished epic branch before the PR.
- **Publishing:** `merge-task.sh` pushes the epic branch to `origin` after each merge, so tracker comments cite
  fetchable commits. Open the epic PR as a draft. Never merge it.

## Test regime

How tests run on this repo, through `bin/pad-test.sh` and the runner's adapter. `/setup-workflow`
step 7g fills it in. `bin/preflight.sh` checks it (`regime`): a repo may add to PAD's managed
values and tighten them, never remove or relax one.

- **Tiers:** none. Today's gates and no cost tiers. Replace this line with a tiers table (below)
  once the repo has a suite map; the managed values below hold either way.
- **Runner:** `none`. The adapter name: `runners/<name>.sh`, PAD's own (`pytest`, `vitest`) or
  the repo's, in `.claude/pad-plugins/runners/`.
- **Repeat limit:** `3`. Runs of one selection on unchanged code (a classifying rerun excluded).
- **Ticket run limit:** `12`. Runs per ticket on changed code.
- **Flaky quarantine:** `8 tests, 7 days`. At most this many tests, for at most this long;
  quarantined tests run and do not gate.
- **Suite map:** `tests/MAP.md`. Only a suite ticket may change it.
- **Protected surface:** none. PAD manages `.claude/workflow/**`, `.claude/settings.json`, CI
  workflow files, `.pre-commit-config.yaml`, the suite map and the adapter's `protected-files`;
  list a repo's additions here as backticked globs. Only a suite ticket may change them
  (`task-submit.sh`: `needs-suite-owner: <path>`).

The tiers table, when there is one:

| Tier | Adapter selector | Per-test kill | Budget | Declared GB | Workers |
|---|---|---|---|---|---|
| fast | `<selector>` | 60 | 5 min | 0.5 | 4 |
| heavy | `<selector>` | 300 | 20 min | 2 | 2 |
| epic | `<selector>` | 900 | 60 min | 4 | 1 |
