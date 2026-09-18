---
name: tickets
description: Turn an approved spec into a work plan of outcome-based tasks with blocking edges, and publish it as an epic and tasks in the configured tracker. Run as /tickets <spec path | epic key>.
argument-hint: "<spec path | epic key>"
disable-model-invocation: true
---

# Spec → tickets

Input: `$ARGUMENTS`. Read, in order:
1. `.claude/workflow/config.md`
2. `.claude/workflow/ticket-template.md`
3. `.claude/workflow/definition-of-done.md`
4. the spec

Every tracker read and write goes through the `tracker` agent, which owns the tracker's tools
and its adapter. You never call the tracker directly.

An epic key means: ask `tracker` to `read-epic` and `read-task` its children, read the linked
spec, and plan only what's missing.

Nothing is published before the operator approves the plan.

## 1. Decompose along outcomes

- **Slice vertically.** Each task delivers one to three of the spec's outcomes end to end and
  is testable on its own. Never split by layer ("models", then "API", then "tests").
- **Cover every outcome.** Each spec outcome lands in exactly one task. Setup, config and
  docs work goes inside the task whose outcome needs it.
- **Declare files.** List the files each task will likely touch. Two tasks that share a file
  cannot run in the same wave, so either give one a `Blocked by` edge or move the shared
  change into an earlier task.
- **Pin interfaces.** When a later task uses what an earlier one builds, write the exact
  names and signatures into both tasks' `Interfaces`. Implementers see only their own ticket.
- **Tag resources.** Mark outcomes that need a serial resource from the config, by its tag.
- **Label hard tasks.** Label a task `complex` when it needs design judgment across modules,
  so `/batch-implement` gives it the stronger model.
- **Size to one session:** as a rule of thumb, at most 3 outcomes and about 5 files.

## 2. Compute waves and show the plan

A task is in wave *n* when all its blockers are in earlier waves. Present one table and stop
for approval:

| Wave | Task | Outcomes | Blocked by | Files | Tags |
|---|---|---|---|---|---|

Below it, list any spec outcome with no task (there should be none) and any decision you made
that the spec didn't state.

## 3. Write the plan file

After approval, write `.work/plans/<slug>.md`: the table, then every task's full body in the
ticket template. The plan file is how a re-run avoids duplicating tickets.

## 4. Publish through the adapter

Send `tracker` one request per step, and record every key it returns in the plan file before
the next step. `tracker` refuses to duplicate an existing epic or task, so a re-run continues
where the last one stopped.

1. **Create the epic** (`create-epic`), or reuse the key you were given. Its description holds
   the problem, the outcomes and the spec path: the working spec is not committed, so the
   outcomes have to live in the tracker too.
2. **Create each task** (`create-task` with the epic as `KEY`) in wave order, body from the
   template.
3. **Replace placeholders.** Now that keys exist, rewrite each `Blocked by` and `Interfaces`
   section to name real keys, and send the corrected bodies back as `update` operations.
4. **Create every blocking edge** (`link`, with the blocker as `BLOCKER`).
5. **Record the epic key** in the spec's header (`Tracker: <key>`).

If `tracker` reports `FAIL`, stop and report what exists, with the keys from the plan file.

## 5. Hand off

Print the epic key, the wave table with keys, and: `/batch-implement <epic key>`.
