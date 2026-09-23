---
name: batch-implement
description: Implement a batch of planned tasks test-first. Unblocked tasks run in parallel in isolated worktrees - tests designed first, then code written against them - and each merges only when the definition of done holds. Tracker status moves as it goes. Run as /batch-implement <epic key | task keys | plan path | outcomes>.
argument-hint: "<epic key | task keys… | plan path | outcomes in quotes>"
disable-model-invocation: true
---

# Tasks → tested, merged code

Input: `$ARGUMENTS`. Read `.claude/workflow/config.md` and
`.claude/workflow/definition-of-done.md`.

You orchestrate and never write product code yourself. You run three layers of agents:

| Agent | Does | Dispatched by |
|---|---|---|
| `task-planner` | Waves, file conflicts, interface mismatches, risks | You, once, before the first wave |
| `epic-merger` | The epic branch's only writer: re-checks, merges, gates, pushes, reverts | You, once, after the baseline |
| `ticket-owner` | One task from `doing` to `done`: its tests, its code, its gates, its ticket and run-log entry | You, one per task |
| `test-designer` | The task's failing tests + stubs, committed red | Its ticket owner |
| `code-writer` | Makes those tests pass, suite and lint green | Its ticket owner |
| `tracker` | Every tracker read and write | Anyone who needs one. You make no tracker calls directly |

You pick the waves, answer what the owners can't settle, run the serial resources, and finish
the epic. A task's detail stays with its owner: you act on one report per task, not every step
of it. Owners and the merger also stop in between — `SUBMITTED`, the merger's per-merge line —
and each stop reaches you as a notification; end that turn without a tool call. That is the
point of the layer — every turn you take re-reads your whole context, so a
task's forty small steps cost far less in an owner's short context than in yours. There is no
code review: a task is done when the definition of done holds.

**Names and addresses.** Give every dispatch a description that names what it works on:
`<epic key>-merger`, `<task key>-owner`. Owners name theirs `<task key>-tests`, `-code` and
`-tracker`. The name is for people reading logs; messages are routed by the agent id each
dispatch returns, so keep the merger's id and every owner's id, and reply to a message at its
`from` address.

**Wait for notifications; never poll.** An agent's report arrives on its own when it stops.
A `sleep`, an `echo`, or a status check while you wait re-reads your whole context for nothing.

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
- the merger stopping with `FAIL`: it holds every task it hasn't answered until you send it
  `CONTINUE`

## 1. Load the work

| Input | Tasks |
|---|---|
| Epic key | `tracker` `read-epic`, then `read-task` for each child that isn't done |
| Task keys | Those tasks, plus any unfinished blockers (ask before pulling in extras) |
| Plan path | The plan file's tasks and their recorded keys |
| Outcomes in quotes | One task, no tracker. Run it inline (3d) on the current branch, after asking: current branch, or a worktree? |

The run id is the epic key or a slug; the run log is `.work/runs/<run id>/progress.md` in the
epic worktree. Owners append their own lines to it, so you only ever append too, one line at a
time with `printf '%s
' '<line>' >> <path>`; longer notes go in
`.work/runs/<run id>/orchestrator.md`.

**Resuming in a new session.** If the run log exists, the earlier run's agents are gone. A task
with a `done`, `failed` or `blocked` line keeps it. A task in the doing status with none of
those starts over — remove any worktree and branch from its earlier attempt
(`git worktree list`) — and that doesn't use up its retry. Start a new merger (2.6).

**After compaction in the same session,** the agents are still running: restart nothing. The
run log's `agents:` lines give you back the merger's id and each owner's; trust the run log and
`git log` over your memory.

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
6. **Start the merger.** Dispatch `epic-merger` as `<epic key>-merger` with the epic branch,
   the run id, the setup, full-suite and lint commands, and the test paths. Append
   `agents: <epic key>-merger <id>` to the run log. It stops with `STARTED`; a `FAIL` means stop
   and ask. There is one merger per session: the epic branch's `git log` is its whole state, so
   a new session starts a fresh one, and nothing else does.

## 3. Run waves until no task is left

**a. Pick the wave.** Ready tasks are those not done whose blockers are all done. Add them in
key order, skipping any whose files overlap a task already in the wave, up to the parallelism
limit.

**b. Dispatch one `ticket-owner` per task, in one message,** so they run in parallel. Name each
`<task key>-owner`, and append `agents: <task key>-owner <id>` to the run log. Each prompt carries: the ticket body verbatim, the task key,
the run id and epic branch, the setup, named-tests, full-suite and lint commands, the config's
test paths, the model for the task and the stronger model for a retry (per the config's
Agents section), any interface correction from an earlier owner's `INTERFACES`, and the
merger's id.

From here each owner moves its ticket, proves red, gates its branch and hands it to the
merger; the merger merges one task at a time and gates the epic head after each merge. You
don't repeat their checks.

**c. Act on the reports.** Owners and the merger each stop with a short block. Act only on:

| Report | You |
|---|---|
| Owner `NEEDS_RULING` | Decide it, log `Ruling: <decision> — <why> — <cost if wrong>`, and `SendMessage` the answer to the owner. If it needs the operator, it's one of the stop-and-ask cases above |
| Owner `MERGED_PENDING_RESOURCE` | Run its `RESOURCE_PROBES`, one at a time across the whole run, with the configured runner, at the merge sha — from a throwaway `git worktree add --detach`, because the merger keeps merging in the epic worktree meanwhile. Keep the output in the run log. Pass: message the owner `RESOURCE PASSED` with the output tail. Fail: message the merger `REVERT <key> <merge sha>`, wait for its `REVERTED` line, then message the owner `RESOURCE FAILED` with the output |
| Owner `DONE`, `FAILED`, `BLOCKED` | Record it. A failed or blocked task's dependents wait; everything else continues. A `BLOCKED` whose note is a `tracker` failure is a stop-and-ask case |
| Merger `FAIL: …; holding …` | Stop and ask. Once the operator has fixed it, message the merger `CONTINUE`; the held owners are still waiting and need nothing from you |

Everything else — an owner's `SUBMITTED`, the merger's `MERGED` / `REJECTED` / `CONFLICT` /
`REVERTED` lines — is for the log; the owner already has it and handles its own retry.

**d. Inline instead** when the whole run is one task: skip the owner and the merger, and do
every role yourself, in order, in the epic worktree (or the current branch for quoted
outcomes). Same gates, same run-log line, and the same tracker comments when there is a
tracker.

**e. Close the wave** when every owner in it has reported `DONE`, `FAILED` or `BLOCKED`.
1. Append a wave line to the run log: the keys, your rulings, and each owner's `INTERFACES`
   and `FILES_OUTSIDE`. The owners have already appended their `<KEY>: done|failed|blocked`
   lines; don't repeat them.
2. Refresh the progress snapshot, unless the adapter is `local` — there the status line reads
   the ticket files directly and a snapshot would only go stale. Overwrite
   `.work/progress.json` in the **main checkout**, not this worktree
   (`git rev-parse --git-common-dir`, then its parent), with the epic's standing counts on one
   line: `{"epic":"<epic key>","done":<n>,"total":<n>,"doing":["<task key>"],"updated":"<ISO-8601 UTC>"}`.
   `total` is the epic's task count, `done` and `doing` the tasks in those configured statuses;
   the status line prints `epic` and `doing` verbatim, so use the tracker's own keys. A
   snapshot older than six hours is shown as stale, so never carry an old `updated` forward.
   Nothing else reads this file — if the write fails, note it and carry on.

## 4. Finish the epic

Once every owner has reported and the merger has answered every `READY`, the merger is idle and
you may commit and push on the epic branch yourself. Final-review fixes (step 2) go back through
it, so write the development record after they land.

1. **Full gates** at the epic head.
2. **Final review.** If config sets a level, run `/code-review <level>`; fix only correctness
   findings, test-first: one `ticket-owner` per fix, dispatched with a slug instead of a ticket
   key, through the same merger. In an inline run, fix them inline.
3. **Development record.** Append an Outcome section to the epic's `docs/decisions/` entry, or
   create one per `docs/decisions/README.md`: what was built, where it departed from the spec,
   and why. Use `Edit` to append and `Write` to create, not a heredoc
   (`.claude/workflow/writing-files.md`). Commit it.
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
