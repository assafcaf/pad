---
name: batch-implement
description: Implement a batch of planned tickets. Unblocked tickets run in parallel, one owner each in its own worktree from start to merged, and each merges only when the definition of done holds. Scripts land the code and keep the ledger. Run as /batch-implement <epic key | task keys | plan path | outcomes>.
argument-hint: "<epic key | task keys… | plan path | outcomes in quotes> [--gate full|affected]"
disable-model-invocation: true
---

# Tasks → tested, merged code

Input: `$ARGUMENTS`. Read `.claude/workflow/config.md` and
`.claude/workflow/definition-of-done.md`.
Run `bash .claude/workflow/bin/rules.sh for orchestrator` and follow every rule it prints
(`.claude/workflow/rules/`).

`--gate full|affected` picks what each merge's gate runs; without it, the config's Execution →
Gate. With `affected`, every `merge-task.sh` call adds `--affected "<named tests>"` (the config's
Run named tests command, `{tests}` left in). With the config's Test workers set, every call adds
`--workers <n>`.

You orchestrate and never write product code yourself, and you never carry a message between
two agents. Your verbs are partition, sequence, land, replan and escalate.

| Agent | Does | Dispatched by |
|---|---|---|
| `owner` | One ticket from start to merged: its tests (unless protected), its code, its gates, its rebase | You, one per ticket |
| `test-designer` | A protected ticket's failing tests + stubs, committed red | Its owner, as a blocking child |
| `tracker` | Tracker reads, ticket creation and links | You only. Owners never dispatch it. Status and comment writes go through `ledger.sh`, for every adapter |
| `memory-curator` | Keeps the agents' persistent memory clean: keeps, tightens, merges or deletes lessons, never adds them | You, once, at the end of the epic |

You pick the waves, land what owners report ready, answer what they can't settle, run the
serial resources, and finish the epic. A ticket's detail stays with its owner: you act on its
one-line report and on each `merge-task.sh`'s last line, nothing else. Every turn you take
re-reads your whole context, so you pay per hand-off: the fewer, the cheaper. Owners settle
interfaces and questions between themselves, by message, without you.

**Names and addresses.** Give every dispatch a description that names what it works on:
`<task key>-owner`. Owners name their test-designer `<task key>-tests`. The name is for people reading logs; messages are routed by the agent id each
dispatch returns, so keep every owner's id, and reply to a message at its
`from` address.

**Wait for notifications; never poll.** An agent's report arrives on its own when it stops.
A `sleep`, an `echo`, or a status check while you wait re-reads your whole context for nothing.

**Keep going without check-ins.** After the start confirmation, don't pause between tasks or
waves. When the tickets don't settle something, decide it and log
`Ruling: <decision> — <why> — <cost if wrong>`. Only these need the operator, as a question:
- an irreversible action outside this flow
- a security-sensitive action
- changing shared state other than the epic branch and its tickets (`main`, a serial
  resource's current state, other tickets)
- a baseline that is already red

**A question parks one task, not the run.** Send the operator a push notification with the
task key and the question, and append it to the run log as `QUESTION <KEY>: <question>` with
`bash .claude/workflow/bin/run-log.sh <run id> "QUESTION <KEY>: <question>"`. Then park only
that task: its owner waits for your answer, and its dependents wait with it — they are not
ready until it is done. A question that belongs to no one task (a red baseline) uses the epic
key. Never call `AskUserQuestion`
for a question: it blocks the whole session until someone answers.

**Everything else keeps moving while a task is parked.** Keep dispatching ready tasks, running
`merge-task.sh` for each `READY` report. The operator answers by typing into this
session while it runs: log the answer as a `Ruling:` line, `SendMessage` it to the parked
owner, which resumes from where it stopped, and fill any slot the unparked task's dependents
open.

**Pause only when nothing is runnable.** When every task left is parked, blocked, failed or
waiting on one of those, and no owner or merge is still in flight, pause the whole run: send one more push
notification saying the run is paused and which questions hold it, append `PAUSED: <keys>` to
the run log, and end your turn. The next answer resumes the run.

**Log every halt with `halt-log.sh`.** When you park a task, and when you pause the run, run
`bash .claude/workflow/bin/halt-log.sh <run id> <KEY> <class> "<cause>" pending`, with `-` as
the key for a run-wide pause. It appends one line to `.claude/agent-memory/orchestrator/HALTS.md`
in the main checkout. The class names where the fix belongs: `pad` (this workflow), `project`
(the product, its tickets or spec), `machine` (this host: a tool, a port, a permission rule) or
`harness` (Claude Code itself). When the halt resolves, log a second line with the same run id,
key, class and cause, and what unblocked it in place of `pending`.

**Test removals go through the rules.** `weakened-tests.sh` passes a removed test only when a
test-removal rule in `.claude/workflow/rules/` explains it (`rules.sh list test-removal`).
Nothing switches the check off: never set its pattern variables to get a merge through, never
add a ruling that excuses a removal, and never edit your own permission settings to get past a
denial; give the operator the rule to add instead. A deletion the operator approves but no
rule explains needs a rule: the operator adds one (a repo rule in the same folder), and the
merge then passes as it is.

## 1. Load the work

| Input | Tasks |
|---|---|
| Epic key | `tracker` `read-epic`, then `read-task` for each child that isn't done |
| Task keys | Those tasks, plus any unfinished blockers (ask before pulling in extras) |
| Plan path | The plan file's tasks and their recorded keys |
| Outcomes in quotes | One task, no tracker. Run it inline (3d) on the current branch, after asking: current branch, or a worktree? |

**Write each ticket body once,** to `.work/runs/<run id>/tickets/<KEY>.md` in the epic
worktree, with `Write`, as `tracker` returned it. From here every agent gets the file's
absolute path and reads it, rather than being handed the body as text. Each copy retyped into
a prompt is output that someone waits for, three times per task.

The run id is the epic key or a slug; the run log is `.work/runs/<run id>/progress.md` in the
epic worktree. Owners append their own lines to it, so you only ever append too, one line at a
time with `printf '%s
' '<line>' >> <path>`; longer notes go in
`.work/runs/<run id>/orchestrator.md`.

**Resuming in a new session.** If the run log exists, the earlier run's agents are gone. A task
with a `done`, `failed` or `blocked` line keeps it. A task in the doing status with none of
those starts over — remove any worktree and branch from its earlier attempt
(`git worktree list`) — and that doesn't use up its retry. A task whose `Merge <KEY>` commit is
on the epic branch but has no `done` line isn't restarted: gate the epic head, push, and
record it done with `ledger.sh <KEY> status done "<comment>" --run <run id> --sha <sha7>`.

**After compaction in the same session,** the agents are still running: restart nothing. The
run log's `agents:` lines give you back each owner's id; trust the run log and
`git log` over your memory.

## 2. Start

1. **Plan.** Run `bash .claude/workflow/bin/plan-check.sh <the run's ticket dir>`. It
   computes what a planner used to: `OVERLAPS` and `PROTECTED` mismatches (planning errors: send
   them back to `/tickets`), `HOTSPOTS`, `SWEEPS` and the `CRITICAL-PATH`. Waves follow the
   tickets' `Depends on`.
2. **Confirm once.** Show the waves with each ticket's Protected flag, the critical path, the
   epic branch name, the script's hotspots, and that you will push that branch and update the
   tracker as tickets land. Wait for yes.
3. **Enter the epic worktree.** Create it if missing (`git fetch origin`, then
   `git worktree add .claude/worktrees/<KEY> -b <epic branch> origin/HEAD`), then
   Never call `EnterWorktree`: it
   moves your session and strands the agents you resume. Reach the epic worktree with
   `git -C .claude/worktrees/<KEY> <command>`, and pass that path to every agent.
4. **Check the base setting:** `.claude/settings.json` must set `worktree.baseRef` to `head`,
   or agents branch from the default branch and miss earlier tasks. Stop if it's missing. Even
   when set, `head` is the orchestrator's head: if you don't sit in the epic worktree it
   resolves to the default branch, so owners check their base (owner.md, Procedure step 1).
5. **Baseline.** Run setup, then `bash .claude/workflow/bin/preflight.sh` in the epic worktree.
   It proves the setup still holds: git moves and every unattended command allowed, knowledge
   paths resolve, config sections match the PAD version, dependency directory, agent models,
   executable scripts, `.gitignore`. On `PREFLIGHT FAILED <n>`, stop before any wave and show
   the operator its `PREFLIGHT FAIL` lines (an old PAD version names `/setup-workflow upgrade`).
   Then run the full suite and lint. Log the results with the head sha. Red
   means stop: later failures can't be attributed. Once green, start each configured preview with
   `bash .claude/workflow/bin/preview.sh start --surface <name> --worktree <epic worktree>` (a
   surface with no `Preview start` is a no-op), so each merge shows up live for the operator. Don't
   restart it yourself: `merge-task.sh` stops a running preview before setup and starts it again
   whenever a merge touches the surface's `Restart when changed` paths.

## 3. Run waves until no task is left

**a. Fill the free slots.** Ready tasks are those not done whose blockers are all done. Start
them all in key order, or up to the config's parallelism cap if it sets one, skipping only
nothing: tickets own disjoint files, and shared files are `Touches`, additions only, which
`merge-task.sh` merges. A real conflict comes back as `CONFLICT` and the owner rebases. Don't wait
for a whole wave to close. Whenever a ticket merges or fails, start whatever is ready now. The
waves are the plan's order, not a barrier.

**b. Dispatch one `owner` per ticket, in one message,** so they run in parallel. Name each
`<task key>-owner`, append `agents: <task key>-owner <id>` to the run log, and mark it doing
(3f). Each prompt carries only: the ticket file's absolute path (not its text), the task key,
the run id and epic branch, the
setup, named-tests, typecheck and lint commands, and the config's test paths.

From here each owner writes, proves red, gates, submits and rebases its own branch, and
reports one line. You land it with `merge-task.sh`, which takes the merge lock, so tickets
merge one at a time, each gated on the head the one before produced. You don't repeat the
owner's checks, and you don't review its test removals: `merge-task.sh` runs
`weakened-tests.sh`, which passes a removal only when a rule explains it.

**c. Act on the reports.** Each owner report is one line; each `merge-task.sh` run ends with one
last line. Act only on:

| Report | You |
|---|---|
| Owner `READY <KEY> <TASK_HEAD> <RED>` | Run `bash .claude/workflow/bin/merge-task.sh --worktree <epic worktree> --branch <epic branch> --setup "<setup>" --gate "<full suite>" --typecheck "<typecheck>" --lint "<lint>" --test-paths "<test paths>" [--derived "<path>=<cmd>" …] --protected "<the config's Protected paths>" --ticket <ticket file> --run <run id> --outcomes "<O ids>" <KEY> <RED> <TASK_HEAD> "<the ticket's title>"`, one `--derived` per row of the config's Derived files, in the background (`run_in_background`), and end your turn. That is the whole hand-off: one turn |
| `merge-task.sh` `MERGED <sha>` | Nothing to write: the script recorded it (3e). If the owner's report listed `RESOURCE_PROBES`, run them (below). Fill the free slot (a) |
| `merge-task.sh` `CONFLICT …` or `REJECTED …` | `SendMessage` the owner that line unchanged. It rebases or fixes, re-gates and reports `READY` again |
| `merge-task.sh` `REJECTED` whose failing tests all sit in files the task didn't touch and doesn't import | A false positive: the script already reran them once. Rerun `merge-task.sh` once in the background with the same `RED` and `TASK_HEAD`; the owner hears only the rerun's last line |
| `merge-task.sh` exit 2 (`ERROR <KEY>: …`) | Infrastructure, not the ticket. Run it once more, from a fresh start in the background; when the error says the merge is committed locally, the fresh start is the config's `push-epic` move instead. A second `ERROR` is a question (above): park that ticket |
| Owner `NEEDS_RULING <KEY> <question>` | Decide it, log `Ruling: <decision> — <why> — <cost if wrong>`, and `SendMessage` the answer to the owner. If it needs the operator, it's a question (above): park the ticket |
| Owner `FAILED <KEY> <why>` | Record it (3e). Its dependents wait; everything else continues. A ticket that fails twice is replanned (split, re-referenced, or re-scoped) through `/tickets`' lint, never re-dispatched as it is |

**Resource probes.** After `MERGED`, run the owner's `RESOURCE_PROBES` one at a time across the
whole run, with the configured runner, at the merge sha, from a throwaway
`git worktree add --detach`. Keep the output in the run log. On a failure, once no
`merge-task.sh` is running, revert that merge in the epic worktree with the `revert-merge` move (`config.md`, `## Git moves`),
run the full suite and lint there, push with `push-epic`, and send the owner `RESOURCE FAILED`
with the output tail: it fixes and reports `READY` again. A serial-resource failure is the only
reason a merge is ever reverted.

A flake that forces reruns is fixed at its cause (`.claude/workflow/testing.md`, "Pass under
load"), not rerun again.

**d. Inline instead** when the whole run is one task: skip the owner, and do its procedure
yourself (`.claude/agents/owner.md`), landing it with `merge-task.sh`, in the epic worktree (or
the current branch for quoted outcomes). Same gates, same bookkeeping.

**e. Record each finished task.**
1. A merged task is already recorded: the `merge-task.sh --run` that merged it wrote its
   evidence file, its run-log line, the ticket's `done` status and its `board.md` row, and
   printed its PR-table row. Write none of those again. A `BOOKKEEPING FAIL` line in that
   merge's output is a write to make again before the PR (step 4). For `FAILED`, one
   `run-log.sh` line with the key, the owner's reason and your rulings is enough.
2. Refresh the progress snapshot, unless the adapter is `local` — there the status line reads
   the ticket files directly and a snapshot would only go stale. Overwrite
   `.work/progress.json` in the **main checkout**, not this worktree
   (`git rev-parse --git-common-dir`, then its parent), with the epic's standing counts on one
   line: `{"epic":"<epic key>","done":<n>,"total":<n>,"doing":["<task key>"],"updated":"<ISO-8601 UTC>"}`.
   `total` is the epic's task count, `done` and `doing` the tasks in those configured statuses;
   the status line prints `epic` and `doing` verbatim, so use the tracker's own keys. A
   snapshot older than six hours is shown as stale, so never carry an old `updated` forward.
   Nothing else reads this file — if the write fails, note it and carry on.

**f. Ledger writes are scripts.** Owners never dispatch `tracker`, and no agent writes a status
by hand. At dispatch (b), run `bash .claude/workflow/bin/ledger.sh <KEY> status doing "<run id>,
<epic branch>" --run <run id> --owner <owner's agent id>` from the epic worktree.
`merge-task.sh --run` moves a merged task to `done`. On `FAILED`, run
`ledger.sh <KEY> comment "<the owner's reason>" --run <run id>` and leave the status at
`doing`. `ledger.sh` writes through the configured adapter: local files, `gh`, or the Jira REST
API (`.claude/workflow/trackers/<adapter>.md`). A `LEDGER FAIL` never stops the run: log the
write it missed with `run-log.sh`, carry on, and make the missed writes again before you open
the PR (step 4).

## Review checkpoints

Read `Cadence` under `## Review` in `.claude/workflow/config.md`: `after-first-wave`,
`per-wave`, `end-only` or `none`. At each checkpoint the cadence names (after the first wave,
after every wave, or never for `end-only` and `none`), write a review packet to
`.work/runs/<id>/review-<n>.md`, with `<n>` counting up from 1. The packet lists:

- what merged since the last checkpoint (task keys and merge shas);
- the surfaces those tasks touched;
- how to look at each surface: the command or URL to open it;
- what is unverified: outcomes no gate or check covered;
- what is operator-run: serial resources and live checks only the operator can do.

Then send the operator a push notification saying the review packet is ready, using the same
notification path as a parked question (above). A checkpoint does not stop the run: keep
filling slots and running waves without stopping while the operator reads.

Each finding the operator returns becomes a `fix-<slug>` task in the same run, with its own red
red test first, and goes through `merge-task.sh` like any task. The final review at the end of the
epic (step 4) is unchanged.

## 4. Finish the epic

Once every owner has reported and no `merge-task.sh` is running, you may commit and push on the
epic branch yourself. Final-review fixes (step 2) land through `merge-task.sh` like any task, so refresh the knowledge layer and write the development record after they land.

1. **Full gates** at the epic head, even under `gate=affected`: the full suite and lint, then `bash .claude/workflow/bin/surface-checks.sh`: any
   `SURFACES FAIL <surface>` line fails the gate. Then stop each preview started at the baseline with
   `bash .claude/workflow/bin/preview.sh stop --surface <name> --worktree <epic worktree>`, so it
   holds no file in the worktree.
2. **Final review.** If config sets a level, run `/code-review <level>`; fix only correctness
   findings, test-first: one `owner` per fix, dispatched with a slug instead of a ticket
   key, landed by `merge-task.sh`. In an inline run, fix them inline.
3. **Knowledge refresh.** Only when the config's `## Project knowledge` section is `Mode: on`.
   Run `/knowledge-layer refresh` against the epic head. Approve its cited lines (terms,
   modules, paths, overlaps) as a ruling; What this repo is, Invariants and Pitfalls stay as
   they are. A doubt about them, or a blocker whose answer was already an Invariant, goes in
   the PR body for the operator. Commit the result on the epic branch. Do not edit those
   files yourself: a line the operator did not write is the kind that measures worse than no
   line at all.
4. **Development record.** Append an Outcome section to the epic's `docs/decisions/` entry, or
   create one per `docs/decisions/README.md`: what was built, where it departed from the spec,
   and why. Use `Edit` to append and `Write` to create, not a heredoc
   (`.claude/workflow/writing-files.md`). Commit it.
5. **Curate the agents' memory.** Dispatch `memory-curator` as `<epic key>-memory` with the
   epic worktree's path, the epic branch and the run log's path, and wait for its report.
   Agents added lessons to their memory during the run (`.claude/workflow/agent-memory.md`).
   The curator keeps, tightens, merges or deletes them, and commits the result on the epic
   branch. A `BLOCKED` doesn't stop the epic: note it for the PR body.
6. **Push and open a draft PR** (`gh pr create --draft`) whose body has the epic link, a table
   of tasks (key, outcomes, merge sha), the rulings, failed or blocked tasks, what was not
   verified, a **Test removals** section (every `REMOVALS` line from the run log: the test, the
   rule that explains it, from `merge-task.sh`'s `REMOVALS <KEY>:` lines), and an **Agent memory** section: the curator's `CHANGED` lines, its
   `PROJECT_MD_CANDIDATES` (for the operator to add to `project.md` or drop), its
   `UPSTREAM_FIXES`, its `LOCAL_CANDIDATES` (for `CLAUDE.local.md`) and its
   `REPEATED_RULINGS` (questions for the next `/tickets`), each group listed separately. Then have `tracker` move the epic to the review status and comment the PR
   URL. Stop the local app if you started one.
7. **Report:** the PR URL, done / failed / blocked counts, and every `Ruling:` line — those are
   the decisions you made on the operator's behalf.
