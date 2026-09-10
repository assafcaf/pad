# Dispatch

Per-repo configuration for the `/dispatch` skill — the manager that runs a batch of related
work with one agent per unblocked task. The skill holds the process and the reasoning; this
file holds the values. Edit them here rather than in the skill.

## Vocabulary

A **run** is one batch of related work. A **task** is one unit inside it. Neither word implies
a tracker: a run is a tracker epic, a parent with subtasks, or a piece of work someone
described in prose, and the machinery is the same for all three.

| Term | Is |
|---|---|
| run | the whole batch, and the unit of a `/dispatch` invocation |
| task | one unit of work inside a run — a tracker item, or an entry the planner derived |
| wave | the set of tasks dispatched concurrently, drawn from the frontier |
| blackboard | `docs/dispatch/<run-id>/` — where every agent writes for every other agent |

### Identity

`<run-id>` and `<task-id>` are the tracker's keys when the work came from a tracker
(`PROJ-17`, `PROJ-22`). When it did not, the planner derives short kebab-case slugs and records
them at the top of `plan.md`, which is then the only place any agent resolves an id from.

Ids reach branch names and paths, so they stay `[a-z0-9-]` plus the tracker's own capitals.

## Concurrency

| Knob | Value | What it controls |
|---|---|---|
| `max_tasks_per_wave` | **5** | Task agents dispatched in one wave. The frontier is often narrower than this, so it is a ceiling, not a target |
| `review_rounds` | **3** | Worker↔reviewer rounds a task agent runs before it escalates a disagreement |
| `worker_escalations` | **1** | Times a task agent may replace its worker with a fresh one a tier up, when the worker cannot see its own problem |
| `ruling_rounds` | **1** | Rounds a task agent gets to apply a manager's ruling before returning `blocked` |

**Raising `max_tasks_per_wave` costs more than it looks.** Every extra concurrent task is
another diff meeting the others at integration, and another entry in the planner's collision
matrix — which grows as pairs, not as tasks. Five is a working ceiling for this repo, not a
limit of the tooling.

## Models

**The planner assesses, the manager decides.** `plan.md` carries a complexity line per task
with a one-sentence rationale; the manager reads that line and names the model. There is no
fixed table to fall out of date, because complexity is a property of the task, not of a
category someone guessed at in advance.

Turn count beats token price: a model that takes three times the turns costs more than the
tier above it. The cheapest tier earns its place only where the acceptance criteria are
complete enough that implementation is transcription plus testing.

Starting points, to be overridden by what `plan.md` actually says:

| Role | Typical | Why |
|---|---|---|
| Deep planner | `opus` | Runs once; every task inherits its output |
| Drift planner | `haiku` | Reads the plan and the blackboard's summaries; opens no diff |
| Task agent | `sonnet` | Orchestrates and judges; writes no code |
| Implementation worker | per `plan.md` | The one genuinely variable seat |
| Reviewer | scale to the diff | A mechanical change does not need `sonnet`; subtle stream handling wants more |
| Integrator | `sonnet` | Merges, resolves conflicts, reads gate output |
| Final whole-branch review | `opus` | Last gate before the run is handed over |

**Every dispatch names a model.** An omitted model inherits the caller's, which is the most
expensive one on the board — that single omission is what quietly defeats the whole policy.

## Nesting depth

Subagents may nest **3 levels below the main session**, and a run consumes exactly that:

    manager (main) → task agent (1) → worker (2) → /review-standards-spec's agents (3)

Level 3 cannot spawn. If a worker's toolchain needs to go deeper, raise
`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` rather than flattening the run.

## Branches and paths

| Knob | Value |
|---|---|
| Run branch | `dispatch/<run-id>` |
| Task branch | `<run-id>/<task-id>` |
| Worktree root | `.claude/worktrees/` — gitignored, per `CLAUDE.md` |
| Run worktree | `.claude/worktrees/<run-id>` — the run branch's; planners and integrators work here |
| Task worktree | `.claude/worktrees/<task-id>` — one per task agent, removed once its task is merged |
| Blackboard | `docs/dispatch/<run-id>/` — committed on the run branch, removed in its final commit |
| Report | `dispatch-report.md` in the manager's worktree root, uncommitted |

The run branch is the only branch the manager writes to. `develop` and `main` are the user's,
and reaching them is one of the skill's four hard stops.

## Mechanics that have cost a run

Each of these was learned by hitting it during the `PROJ-17` run. They are recorded here because
the run that found them could not record them: the skill was untracked at the time, so its
report could only note them and move on.

**The manager stays where it was invoked.** It creates the run branch's worktree but does not
enter it — a manager pinned inside a worktree pins every agent it spawns to that same worktree,
and in `PROJ-17` the first worker lost its shell entirely and produced nothing. The manager
drives the run branch with `git -C <worktree>` and absolute paths; the integrator is the agent
that works inside it.

**Every dispatched agent calls `EnterWorktree` with its own path as its first tool call**, with
a `cd`-prefix fallback if it errors. Every prompt template here says so; keep it there.

**Heredocs mangle backticks.** Even a quoted `<<'PY'` gets re-evaluated by the Bash wrapper on
this host, so backticks in the payload run as command substitution and silently strip the text
between them. Prose full of `code spans` — which is most of what this skill's agents write —
goes through the Write and Edit tools. Long heredocs into files have also hung here.

**Finished worktrees get removed, branches kept.** `git worktree remove .claude/worktrees/<id>`
once a task is merged and its gate is green. The branch stays, because the merge commit
references it. `CLAUDE.md` records that accumulated worktrees have caused real damage in this
repo — on 2026-09-07 unwinding three of them detached the root checkout's HEAD.

## The blackboard

`docs/dispatch/<run-id>/`, committed on the run branch so every worktree can read it after a
merge. It is working state, not project history: **the run's final commit removes the whole
directory**, so nothing reaches `develop` or `main`.

    docs/dispatch/<run-id>/
      plan.md                        deep planner, once, then frozen
      drift/wave-<n>.md              drift planner, one per wave from 2 on
      tasks/<task-id>/
        established.md               what this task fixed for later tasks
        report.md                    the worker's full account
        review.md                    the reviewer's full findings
        verdict.md                   the task agent's outcome
      rulings/<task-id>.md           the manager, on escalation
      final-review.md                the whole-branch reviewer, once, at the finish

**One writer per path.** No file is ever edited by two agents, so parallel task branches merge
without conflict. A task agent writes only under its own `tasks/<task-id>/`; the manager writes
only under `rulings/`; the planner owns `plan.md` and `drift/`.

`plan.md` is **frozen** once written. The drift check compares reality against it, and a plan
edited into agreement with what happened can no longer detect anything.

### Frontmatter

Every blackboard file opens with this header, so an agent can filter mechanically instead of
reading prose:

    ---
    run: <run-id>
    task: <task-id>          # omit on run-level files
    role: planner | task-agent | worker | reviewer | integrator | manager
    kind: plan | drift | established | report | review | verdict | ruling | final-review
    status: <see below>
    wave: <n>
    written: <ISO 8601>
    ---

`status` by `kind`:

| `kind` | `status` |
|---|---|
| `verdict` | `agreed` · `disputed` · `blocked` |
| `drift` | `on-plan` · `off-plan` |
| `plan`, `established`, `report`, `review`, `ruling`, `final-review` | `final` |

This is what lets the manager answer "what needs me?" with a grep over `status:` lines, having
opened no bodies — and what lets it rebuild that answer after a compaction.

## The integration gate

The command the integrator runs on the run branch **after every merge**. Two task branches that
are each green alone can be red together, and this is what catches it.

    timeout 420 uv run pytest -q -rs

**This command does not work on every branch.** It needs `pyproject.toml` and `uv.lock`; where
they are absent the gate has nothing to run. An integrator reaching that records a ruling
saying the gate was unavailable rather than reporting a pass it did not observe.

### Running the gate on the GPU box

Every execution in this repo happens on the box, per `CLAUDE.md`. **`remote-dev` is the
authority on reaching it** — the SSH invocation and its flags, the `bash -lc` PATH requirement,
and the `updateInstead` push. Take the invocation from there.

Two things it does not cover, because they are specific to a run branch:

- **Push a refspec, not `HEAD`.** `remote-dev` documents pushing `HEAD` to the branch the box
  has checked out. The box's checkout stays on `develop` and must not be dragged onto a run
  branch, so push the ref instead — this moves a ref and leaves the box's tree alone, giving
  `updateInstead` nothing to reject:

      git push box "dispatch/<run-id>:refs/heads/dispatch/<run-id>"

- **Gate in a worktree of its own on the box**, `~/dispatch/<run-id>`, created once and reused,
  reset hard to the pushed ref before each gate. The box's own checkout is never touched.

The box has **no GitHub access** by design — `git ls-remote origin` fails there. `git push box`
is the only sync path, so nothing on the box can pull.

## Task source

The tracker is **Jira**, project `PROJ`, read through the `atlassian` MCP server. The blocking
graph is native `Blocks` links. See `issue-tracker.md` for the tools, the JQL, and the frontier
query.

A run **may have no tracker at all**. When the work arrived as prose, `plan.md` is the task
list and each task's acceptance criteria are the planner's, not a ticket's. Everything
downstream reads "the task's acceptance criteria" and does not care which of the two supplied
them.

### Writing back

Where a task **does** have a tracker item, its task agent transitions it:

| When | To |
|---|---|
| The task agent starts work | `In Progress` |
| The task agent returns a verdict | `In Review` |

**`Done` is the operator's alone**, set after the feature is tested end to end. No agent
transitions a task to `Done`, and a run finishes with its tasks in `In Review`.

A task with no tracker item skips these transitions silently. No agent writes a comment, an
assignment, or any other field.
