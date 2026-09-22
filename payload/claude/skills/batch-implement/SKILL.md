---
name: batch-implement
description: Implement a batch of planned tasks test-first. Unblocked tasks run in parallel in isolated worktrees - tests designed first, then code written against them - and each merges only when the definition of done holds. Tracker status moves as it goes. Run as /batch-implement <epic key | task keys | plan path | outcomes>.
argument-hint: "<epic key | task keys… | plan path | outcomes in quotes>"
disable-model-invocation: true
---

# Tasks → tested, merged code

Input: `$ARGUMENTS`. Read `.claude/workflow/config.md` and
`.claude/workflow/definition-of-done.md`.

You orchestrate four agents and never write product code yourself:

| Agent | Does | When |
|---|---|---|
| `tracker` | Every tracker read and write | Throughout. You make no tracker calls directly |
| `task-planner` | Waves, file conflicts, interface mismatches, risks | Once, before the first wave |
| `test-designer` | The task's failing tests + stubs, committed red | Phase 1 of each wave |
| `code-writer` | Makes those tests pass, suite and lint green | Phase 2 of each wave |

You prove the work with the gates, merge it, and keep the tracker and the run log true. There
is no code review: a task is done when the definition of done holds.

**Keep going without check-ins.** After the start confirmation, don't pause between tasks or
waves. When the tickets don't settle something, decide it and log
`Ruling: <decision> — <why> — <cost if wrong>`. Stop and ask only for:
- an irreversible action outside this flow
- a security-sensitive action
- changing shared state other than the epic branch and its tickets (`main`, a serial
  resource's current state, other tickets)
- a baseline that is already red
- every remaining task being blocked or failed
- `tracker` reporting `FAIL`, or its tools being unavailable: the run's record would silently
  stop matching the code

## 1. Load the work

| Input | Tasks |
|---|---|
| Epic key | `tracker` `read-epic`, then `read-task` for each child that isn't done |
| Task keys | Those tasks, plus any unfinished blockers (ask before pulling in extras) |
| Plan path | The plan file's tasks and their recorded keys |
| Outcomes in quotes | One task, no tracker. Run it inline (3d) on the current branch, after asking: current branch, or a worktree? |

The run id is the epic key or a slug; the run log is `.work/runs/<run id>/progress.md` in the
epic worktree. If it exists you are resuming: tasks it marks `done` stay done. A task in the
doing status with no `done` line starts over — remove any worktree and branch from its earlier
attempt (`git worktree list`) — and that doesn't use up its retry. After compaction, trust the
run log and `git log` over your memory.

## 2. Start

1. **Plan.** Dispatch `task-planner` with the ticket bodies. Reconcile its waves with the
   tickets' own edges; log a ruling for each disagreement you settle. Its `GAPS` and `RISKS`
   may change the models you choose or send you back to `/tickets`.
2. **Confirm once.** Show the waves, the epic branch name, the planner's conflicts and gaps,
   and that you will push that branch and update the tracker as tasks land. Wait for yes.
3. **Enter the epic worktree.** Create it if missing (`git fetch origin`, then
   `git worktree add .claude/worktrees/<KEY> -b <epic branch> origin/HEAD`), then
   `EnterWorktree` into it.
4. **Check the base setting:** `.claude/settings.json` must set `worktree.baseRef` to `head`,
   or agents branch from the default branch and miss earlier tasks. Stop if it's missing.
5. **Baseline.** Run setup, the full suite and lint. Log the results with the head sha. Red
   means stop: later failures can't be attributed.

## 3. Run waves until no task is left

**a. Pick the wave.** Ready tasks are those not done whose blockers are all done. Add them in
key order, skipping any whose files overlap a task already in the wave, up to the parallelism
limit. Record `BASE = git rev-parse HEAD`. Send `tracker` one request moving each to `doing`
with a comment naming the run and the epic branch.

**b. Phase 1 — tests.** Dispatch every wave task's `test-designer` in one message, so they run
in parallel. Each prompt carries only: the ticket body verbatim, the task key, the setup, named
tests and full suite commands, and any interface correction from an earlier task's report.

For each report:
- `BLOCKED` / `NEEDS_CONTEXT`: answer from the spec or code with SendMessage if you can;
  otherwise log a ruling or mark the task blocked, comment on the ticket, and carry on.
- `DONE`: prove red —
  `bash .claude/workflow/bin/verify-red.sh --setup '<setup>' <RED_COMMIT> -- <named tests>`
  must print `RED OK`. Pass only the host-level outcome tests: a serial-resource outcome
  can't run here and is proven green on its resource instead (3f). A task whose outcomes are
  all resource-tagged has nothing to prove red — log that and move on. Then have `tracker`
  comment: red proven at `<sha7>`, with the outcome → test mapping. That comment is the
  operator's progress signal; don't skip it.
- A task whose red can't be proven goes back to a fresh `test-designer` once, with the output.

**c. Phase 2 — code.** Dispatch `code-writer` for every task that proved red, again in one
message. Each prompt carries: the ticket body, the key, `RED_COMMIT`, the designer's `OUTCOMES`
(the test node ids), `STUBS` and `NOTES`, and the commands.

**d. Inline instead** when the whole run is one task: do both roles yourself, in order, in the
epic worktree (or the current branch for quoted outcomes). Same gates.

**e. Gate each task, in dependency order.**
1. **Tests untouched.** `git diff --name-only <CHERRY_PICKED_RED> <HEAD> -- <test paths>` must
   be empty, where `<test paths>` are the config's test paths, and
   `bash .claude/workflow/bin/weakened-tests.sh <BASE> <HEAD>` must pass.
2. **Merge.** `git merge --no-ff -m "Merge <KEY>: <goal>" <HEAD>`. On conflict:
   `git merge --abort`, requeue for the next wave with the conflicting paths.
3. A failed gate means no merge: requeue once with the gate output, on the stronger model — to
   `code-writer` for a code failure, to `test-designer` for a `BLOCKED` about a wrong test. A
   second failure marks the task `failed`; its dependents wait, everything else continues.

**f. Gate the wave on the epic branch.** Run the full suite and lint. If either is red, revert
the wave's merges newest first (`git revert -m 1 --no-edit <merge>`) until green, and requeue
the reverted tasks with the output; that counts as their retry. Then run each merged task's
serial-resource probes, one at a time, with the configured runner; a failure reverts and
requeues the same way.

**g. Publish the wave.**
1. `git push -u origin <epic branch>`.
2. One `tracker` request: move each merged task to `done`, each with a comment carrying the
   merge and red shas, the outcomes → tests mapping, the red and green commands with
   one-line results, any resource output tail, and files touched outside the ticket's list.
   Comment on failed and blocked tasks too, saying what happened and what is needed.
3. Append to the run log: `<KEY>: done (red <sha7>, merge <sha7>)`, or `failed` / `blocked`
   with the reason, plus each report's `INTERFACES` line.
4. Refresh the progress snapshot, unless the adapter is `local` — there the status line reads
   the ticket files directly and a snapshot would only go stale. Overwrite
   `.work/progress.json` in the **main checkout**, not this worktree
   (`git rev-parse --git-common-dir`, then its parent), with the epic's standing counts on one
   line: `{"epic":"<epic key>","done":<n>,"total":<n>,"doing":["<task key>"],"updated":"<ISO-8601 UTC>"}`.
   `total` is the epic's task count, `done` and `doing` the tasks in those configured statuses;
   the status line prints `epic` and `doing` verbatim, so use the tracker's own keys. A
   snapshot older than six hours is shown as stale, so never carry an old `updated` forward.
   Nothing else reads this file — if the write fails, note it and carry on.
5. Remove each task's worktrees (`git worktree remove`) and branches (`git branch -d`).

## 4. Finish the epic

1. **Full gates** at the epic head.
2. **Development record.** Append an Outcome section to the epic's `docs/decisions/` entry, or
   create one per `docs/decisions/README.md`: what was built, where it departed from the spec,
   and why. Commit it.
3. **Final review.** If config sets a level, run `/code-review <level>`; fix only correctness
   findings, test-first through the same two agents.
4. **Knowledge gaps.** Only when the config's `## Project knowledge` section is `Mode: on`.
   From this run, name what the layer was missing: a term two or more tasks used that
   `CONTEXT.md` does not define, a file every task touched that Standing overlaps does not
   name, a blocker whose answer was already an Invariant. Put the list in the PR body and tell
   the operator to run `/knowledge-layer refresh`. Do not edit those files yourself: a line the
   operator did not write is the kind that measures worse than no line at all.
5. **Push and open a draft PR** (`gh pr create --draft`) whose body has the epic link, a table
   of tasks (key, outcomes, merge sha), the rulings, failed or blocked tasks, and what was not
   verified. Then have `tracker` move the epic to the review status and comment the PR URL.
6. **Report:** the PR URL, done / failed / blocked counts, and every `Ruling:` line — those are
   the decisions you made on the operator's behalf.
