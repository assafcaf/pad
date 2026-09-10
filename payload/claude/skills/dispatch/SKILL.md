---
name: dispatch
description: "Run a batch of related work with a manager and parallel task agents — one per unblocked task, each owning its task end to end, reviewed and merged into a run branch."
disable-model-invocation: true
---

# Dispatch

You are the **manager**. You hold the graph, dispatch agents, rule on what reaches you, and
hand over. You write no code, read no diff, and touch no working tree but your own.

Your context is the run's scarce resource. Everything below exists to spend it on coordination
and nothing else.

## What you read

Four things, all short, all produced for you:

| Source | Carries |
|---|---|
| `plan.md` | the graph, each task's intent and complexity, the collision matrix |
| A task agent's **verdict block** | one task's outcome, in a few lines |
| An integrator's **report line** | what merged, where the branch is, whether the gate is green |
| An **escalation** | one question a task agent could not settle |

Specs, task bodies, diffs, reviews and worker reports are written for other agents, not for
you. They live on the blackboard, and the agents that need them read them there.

## Setup

1. Read `docs/agents/dispatch.md`. It holds every value this run needs — the wave ceiling, the
   round caps, the model policy, the branch and path patterns, the blackboard's layout and
   frontmatter, and the integration gate's command. This skill holds the process and the
   reasoning; that file holds the numbers, and it is the one to edit when they are wrong.
2. Create the run branch's worktree and branch it from the current branch, both named as that
   file specifies. The repo root is someone's live workspace, per `CLAUDE.md`.

   **Stay where you were invoked** and drive that worktree with `git -C <worktree>`. A manager
   pinned inside a worktree pins every agent it spawns to the same one; `docs/agents/dispatch.md`
   has the incident. Planners and integrators are the agents that work inside it.
3. Dispatch the **deep planner**, from [`planner-prompt.md`](planner-prompt.md). It reads the
   spec, every task, and the repo's own instructions; you read its `plan.md`.

You are given a tracker key, several, or a description of work. All three become a run of
tasks, and only the planner needs to know which it was.

## The record is git

You keep no ledger. The durable record of a run is the **run branch's history**: one merge
commit per accepted task, naming the task and carrying every ruling you made about it.

This matters after a compaction. `git log` on the run branch is what survives; your
recollection is not. Trust the log, and the blackboard's `status:` lines.

## The frontier

The **frontier** is every task that is open, unclaimed, and has no blocker still outstanding.
It is the only set you may dispatch from, and you recompute it after every wave.

The tracker's status — or `plan.md`, for a run without one — is your *starting* truth. Once
the run begins, a task is done when its merge commit is on the run branch and not before.

## Dispatch a wave

**From wave two on, check for drift first.** Dispatch the drift planner from
[`drift-prompt.md`](drift-prompt.md); it reads `plan.md` and the blackboard's current state and
answers one question: is the run still inside its plan? An `off-plan` verdict is yours to rule
on before anything else is dispatched.

Then, for each frontier task up to the wave ceiling, dispatch one **task agent** from
[`task-agent-prompt.md`](task-agent-prompt.md) — all in a single message, so they run
concurrently. The frontier is often narrower than the ceiling; dispatch what it holds.

Each task agent gets its own worktree branched from the run branch, named as
`docs/agents/dispatch.md` specifies. Record the branch name and the base commit for each.

**Name each agent's model explicitly.** Read the task's complexity line in `plan.md` and choose
from it. An omitted model inherits yours, which is the most expensive one on the board.

The planner already wrote the **collision matrix** — which frontier tasks touch the same files
and interfaces. Where a pair overlaps, dispatch the earlier task alone this wave and let the
other take the next one. You are reading a matrix, not building one.

A task agent owns its task end to end: it spawns its own implementation worker and its own
independent reviewer, runs their rounds, moves the tracker item to `In Progress` and then
`In Review`, writes everything to the blackboard, and returns you a verdict block.

## Rulings

A running dispatch does not wait on a human. Decide, say what it costs if you are wrong, and
keep going. Record it in `rulings/<task-id>.md` and in the merge commit, so it survives your
context.

Three things reach you, and a task agent settles everything else itself:

- **Cross-task impact** — a change to an interface another task depends on. You hold the graph;
  this one is genuinely yours.
- **A deadlock** — worker and reviewer still disagree after the round cap.
- **A hard stop** — see below.

Constants, naming, file placement, cosmetics, scope calls, and anything answerable by reading
the repo or the blackboard are the task agent's. If one reaches you anyway, rule on it in one
line and say in the ruling that it was below the bar, so the pattern is visible at hand-over.

You rule from the verdict block and the escalation. Where that is genuinely not enough, ask the
task agent for the specific fact you are missing — reading the diff yourself is how a manager
becomes a slow, worse reviewer.

## Integrate the wave

When a wave's task agents have all returned, dispatch **one integrator** from
[`integrator-prompt.md`](integrator-prompt.md). It merges that wave's accepted tasks into the
run branch in dependency order, runs the integration gate after each merge, resolves conflicts,
dispatches its own fixer when the gate goes red, and returns you a report line.

Merging is delegated because its cost has no ceiling. Most merges are trivial; the one that is
not would take your context with it.

## Four things stop you

Stop and ask when you reach one of these, and only these:

- A merge or push to a **shared branch** — `develop`, `main`, anything that is not the run
  branch you created.
- An irreversible or destructive operation.
- A security-sensitive action.
- A task so broken that every path forward is a guess.

Everything else is a ruling.

## Finish

When the frontier is empty, or every remaining task is blocked on something outside this run:

1. Dispatch one final whole-branch review of the run branch, on the model
   `docs/agents/dispatch.md` names for it, pointed at the merge-base with the branch you started
   from. It writes `final-review.md` to the blackboard and returns its findings as a list.
2. Dispatch the **final integrator**, telling it that this is the last integration. Hand it the
   path to `final-review.md`. It gives every finding to **one** fixer as a single list, re-runs
   the gate, and removes the blackboard in the run's last commit.

   **Dispatch it even when there is nothing left to merge.** Its closing jobs are the review
   fixes and the blackboard removal, and a run that skips it hands over a branch nobody can
   merge without knowing to clean up first.

   One fixer per finding rebuilds context and re-runs the gate each time, which costs more than
   the tasks did. And the fixer's work reaches the run branch the same way everything else did —
   through an integrator that gates it.
3. Write the report to the path that file specifies, leave it uncommitted, and name its path in
   your final message.

The report carries: each task and the commit range that closed it; each task left open and what
blocks it; the gate's final result; **every ruling you made, in order, each with what it costs
if wrong**; and the frontier as it now stands.

The ruling list is the only place decisions you took on the user's behalf reach them. It is
exhaustive or it is misleading.

Tasks finish in `In Review`. `Done` is the operator's, after the feature is tested end to end.

## Rationalizations

| Excuse | Reality |
|---|---|
| "The frontier is one task wide, this skill is pointless" | Fresh context per task and an independent review gate are most of the value. Width is a bonus. |
| "I'll fix this finding myself, dispatching is overhead" | A manager's fix reaches the run branch unreviewed. |
| "Both agents only touched one shared file, merging is fine" | That shared file is where the parallel run breaks. The collision matrix is in `plan.md`; read it. |
| "I'll note the rulings at the end from memory" | Compaction takes them. The merge commit and `rulings/` keep them. |
| "I'll skip the drift check, the plan is obviously still good" | Obviously-still-good is the claim the check tests, and it costs one cheap agent. |
