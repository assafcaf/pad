---
name: evidence-dispatch
description: "Run a batch of related work where each acceptance criterion is an executable probe, proven red before the work and green after. Review is spent only where a probe cannot reach."
disable-model-invocation: true
---

# Evidence dispatch

You are the **manager**. You hold the graph, dispatch agents, rule on what reaches you, and hand
over. You write no code and touch no working tree but your own.

**The rule the whole process rests on: no agent asserts anything another agent has to
re-derive.** A claim arrives with the command that proves it, the exit code, and the host it ran
on — or it does not arrive.

## Which skill, this or `/dispatch`

Both run a batch of related work. They differ in what they spend agents on.

| | `/dispatch` | this |
|---|---|---|
| A criterion is met when | a reviewer reads the diff and agrees | a probe exits 0, having exited non-zero at the base commit |
| Findings | an unfiltered reviewer raises them, the worker rebuts, up to 3 rounds | a falsifier ships a command that fails, or returns clean |
| Prose per task | `report.md`, `review.md`, `verdict.md`, `established.md` | `established.md` |
| Suits | work whose correctness lives in judgment | work whose correctness lives on a machine |

**Use this one when most acceptance criteria can be settled by running something.** Building
images, wiring services, collecting data, reproducing a pipeline, anything where the answer is
on disk or on a port. Use `/dispatch` when the criteria are about design — where the question is
"is this the right abstraction", which no probe answers.

Mixing is fine and expected: this skill's `judgment` track is `/dispatch`'s review, narrowed to
one question and one pass.

## Setup

1. Read `docs/agents/evidence-dispatch.md`. It holds every value this run needs — the tracks,
   the knobs, the ledger schema, the standing checks, the gate, the Jira formats. This skill
   holds the process and the reasoning; that file holds the numbers.
2. Create the run branch and, **when the run will ever be wider than one task**, its worktree.
   Branch from the current branch, both named as that file specifies.

   **Stay where you were invoked** and drive the branch with `git -C`. A manager pinned inside a
   worktree pins every agent it spawns to the same one; `docs/agents/dispatch.md` has the
   incident.
3. Dispatch the **deep planner**, from [`planner-prompt.md`](planner-prompt.md). It reads the
   spec and every task, writes `plan.md`, **writes the probes**, and appends the conceptual test
   list to each Jira ticket. You read its return line.

You are given a tracker key, several, or a description of work. Only the planner needs to know
which it was.

## What you read

| Source | Carries |
|---|---|
| `plan.md` | the graph, each task's intent, criteria, probes, complexity, **track**, seams |
| A task agent's **return block** | one task's outcome, in a few lines |
| An integrator's **report line** | what merged, where the branch is, whether the gate is green |
| An **escalation** | one question a task agent could not settle |

Probes, ledgers, logs and diffs are written for other agents and for the record. Do not open
them. The exception is a ruling you cannot make without one specific fact — ask the task agent
for that fact.

## The record is git, plus the ledger

The durable record of a run is the **run branch's history** — one merge or task commit per
accepted task, carrying every ruling — **plus `evidence/<run-id>/`, which is not deleted.**

That directory outlives the run on purpose. `CLAUDE.md`: this phase keeps everything, and the
dataset's provenance is the product. A probe's captured output is provenance.

This matters after a compaction. `git log` and the ledger are what survive; your recollection is
not.

## Dispatch a wave

Recompute the frontier: every task open, unclaimed, with no blocker outstanding. A task is done
when its commit is on the run branch and not before.

**Check the width first.** If the frontier is one task wide — `serial_below` in
`docs/agents/evidence-dispatch.md` — run it **serially**: no task worktree, no integrator, no
drift check. The task agent works on the run branch and commits to it directly.

> On `PROJ-17` the frontier was one task wide in all five waves, and the run still paid for five
> worktrees, six integrators and four drift checks. One GPU box and a dependency chain make that
> shape the norm here, not the exception.

Where the frontier **is** wider, dispatch one **task agent** per task from
[`task-agent-prompt.md`](task-agent-prompt.md), all in one message, each with its own worktree
and branch, and read the planner's **collision matrix** before pairing anything. Where a pair
overlaps, dispatch the earlier alone and let the other take the next wave. Dispatch a drift
check first, from `/dispatch`'s [`drift-prompt.md`](../dispatch/drift-prompt.md) — one cheap
agent, and this skill does not need its own.

**Name each agent's model explicitly**, from the task's complexity line.

## The track decides what runs

Every task carries a track — `execution`, `mechanical`, or `judgment` — and the track decides
which agents exist for it. The table is in `docs/agents/evidence-dispatch.md`.

**You do not choose it.** The planner proposes it, the diff can demote it to `execution`
mechanically, and the task agent may upgrade it. A *downgrade* is the only track move that
reaches you, and it is a ruling.

The thing this buys: a task that ships no code gets no falsifier, no reading pass, and no
review of any kind. Its evidence is its deliverable. `PROJ-31` — a 40-episode collection run,
zero lines of code — took 58 minutes, produced 1,039 lines of blackboard and five findings, all
withdrawn. Under this skill it is an `execution` task and none of that happens.

## Rulings

A running dispatch does not wait on a human. Decide, say what it costs if you are wrong, and
keep going. Record it in the task's commit message, so it survives your context.

Four things reach you:

- **Cross-task impact** — a change to an interface another task depends on.
- **A track downgrade** — a task agent believes its work needs *less* scrutiny than planned.
  Upgrades do not reach you; downgrades do.
- **A probe that cannot be written** — a criterion nobody can make executable. Rule on whether
  it becomes a `judgment`-track reading criterion or leaves the run. Do not let it merge as an
  unproven claim.
- **A hard stop** — see below.

Everything else is the task agent's. If something below the bar reaches you anyway, rule in one
line and say it was below the bar, so the pattern is visible at hand-over.

## Integrate

**Serial run:** there is nothing to integrate. The task agent already committed to the run
branch and ran the gate. Read its return line.

**Wide wave:** dispatch one integrator from `/dispatch`'s
[`integrator-prompt.md`](../dispatch/integrator-prompt.md), with one substitution — the gate is
this skill's, from `docs/agents/evidence-dispatch.md`, and it includes `run-checks.sh`. Tell it
so explicitly, and tell it the blackboard removal at the end removes
`docs/dispatch/<run-id>/` **only**: `evidence/<run-id>/` and `gates/` stay.

## Four things stop you

- A merge or push to a **shared branch** — `develop`, `main`, anything that is not the run
  branch you created.
- An irreversible or destructive operation.
- A security-sensitive action.
- A task so broken that every path forward is a guess.

Everything else is a ruling.

## Finish

When the frontier is empty, or every remaining task is blocked outside this run:

1. **If any task ran on the `judgment` track**, dispatch one **silent-failure audit** from
   [`silent-failure-prompt.md`](silent-failure-prompt.md), on `opus`, pointed at the merge-base
   with the branch you started from. One narrow question over the whole run branch. If no task
   was `judgment`, skip it and say in the report that you did.
2. Dispatch one **falsifier** over the whole run branch from
   [`falsifier-prompt.md`](falsifier-prompt.md), unless every task in the run was `execution`.
   Whole-branch, because the classes it catches — a citation into a deleted directory, a
   documented command that fails on a fresh clone — are cross-task and invisible from inside one
   ticket. This is where `PROJ-17`'s only Critical came from.
3. Hand both agents' output to **one fixer** as a single list — a fresh worker from
   [`worker-prompt.md`](worker-prompt.md), told it is closing findings, not building a task.
   One fixer per finding rebuilds context and re-runs the gate each time, which costs more than
   the tasks did.
4. Re-run the gate. Remove `docs/dispatch/<run-id>/` in the run's last commit. **Leave
   `evidence/<run-id>/` and `gates/` in place** — they are the run's manifest and its probes,
   and they are the reason anyone can believe the run later.
5. Write the report to the path `docs/agents/evidence-dispatch.md` specifies, leave it
   uncommitted, and name its path in your final message.

The report carries: each task, its track, and the commit that closed it; each task left open and
what blocks it; the gate's final result; **every ruling you made, in order, each with what it
costs if wrong**; every criterion that ended `cannot verify` and why; and the frontier as it now
stands.

Tasks finish in `In Review`. `Done` is the operator's, after the feature is tested end to end.

## Rationalizations

| Excuse | Reality |
|---|---|
| "The criterion is obviously met, a probe is ceremony" | Then it is a one-line probe. The cost of writing it is smaller than the cost of one agent re-deriving it from prose, and that re-derivation is 37% of the `PROJ-17` clock. |
| "I'll skip the red run, the probe clearly works" | A probe with no red run is a probe nobody has seen fail. `PROJ-17` shipped `tests/test_compose.py:211-221`, which could not fail for the flag it existed to guard. |
| "This finding is real even without a reproduction" | Then it belongs to the silent-failure audit, which is the one place an argument counts. Everywhere else, 21 of `PROJ-17`'s 25 findings were withdrawn by their own author. |
| "The frontier is one wide, but worktrees are safer" | Worktrees are the isolation you need for concurrency. With none, they are three extra failure modes; `CLAUDE.md` records worktree unwinding detaching the root checkout's HEAD. |
| "Evidence proves the code is right" | It proves the code did this, here, once. `PROJ-29`'s publisher passed every test and was correct only by coincidence. That is the `judgment` track's whole job. |
| "I'll post the evidence comment from what the worker told me" | Post it from the ledger. A comment sourced from an agent's summary is the re-derivation this skill exists to delete. |
