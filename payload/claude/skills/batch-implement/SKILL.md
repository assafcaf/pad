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
| `memory-curator` | Keeps the agents' persistent memory clean across agents: keeps, tightens, merges, copies or deletes lessons, never invents them; proposes harness changes | You, once, at the end of the epic, after the run review |

You pick the waves, answer what the owners can't settle, run the serial resources, and finish
the epic. A task's detail stays with its owner: you act on one report per task, not every step
of it. Owners and the merger also stop in between — `SUBMITTED`, the merger's per-merge line —
and each stop reaches you as a notification; end that turn without a tool call. The one
in-between message you do act on is an owner's `READY`: you relay it to the merger (3c). That is the
point of the layer — every turn you take re-reads your whole context, so a
task's forty small steps cost far less in an owner's short context than in yours. There is no
code review: a task is done when the definition of done holds.

**Names and addresses.** Give every dispatch a description that names what it works on:
`<epic key>-merger`, `<task key>-owner`. Owners name theirs `<task key>-tests`, `-code` and
`-tracker`. The name is for people reading logs; messages are routed by the agent id each
dispatch returns, so keep the merger's id and every owner's id, and reply to a message at its
`from` address.

**Only you message the merger.** An agent resumed by a message comes back carrying the
sender's context: its stop is delivered to the sender, and a sender running in an isolated
worktree can leave it sandboxed there. A merger resumed by a worktree-isolated owner lost git
in the epic worktree twice in one run, the replacement included. So owners hand their `READY`
to you and you relay it; the merger replies to owners, never the other way round.

**Reports come by message.** An owner is resumed by the merger and by its own agents, so its
stop can reach one of them instead of you. Every dispatch of the merger and of an owner
carries your own address — `main`, the address `SendMessage` gives the main conversation — and
they send you each report that needs you before stopping with it. The same report can then
reach you twice, as the message and as the stop: act on the first, per task and status, and
ignore the repeat.

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
- the merger stopping with `FAIL: branch`: it holds every task it hasn't answered until you
  send it `CONTINUE`. A `FAIL: environment` is not asked about: replace the merger (3c)

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
epic worktree. Owners and the merger append their own lines to it, so you only ever append too,
one line at a time, **stamped with the time at the end**:
`printf '%s @%s\n' '<line>' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> <path>`. Every writer stamps
its lines this way; the stamp goes last because the status line matches each line's start.
Longer notes go in `.work/runs/<run id>/orchestrator.md`. Agents record what held them up
outside their own work in `.work/runs/<run id>/incidents.md`
(`.claude/workflow/agent-memory.md`, "A memory line or a finding"); so do you, for a report
that never reached you or a wait on the operator.

**Resuming in a new session.** If the run log exists, the earlier run's agents are gone. A task
with a `done`, `failed` or `blocked` line keeps it. A task in the doing status with none of
those starts over — remove any worktree and branch from its earlier attempt
(`git worktree list`) — and that doesn't use up its retry. Start a new merger (2.6).

**After compaction in the same session,** the agents are still running: restart nothing. The
run log's `agents:` lines give you back the merger's id and each owner's; trust the run log and
`git log` over your memory.

## 2. Start

1. **Plan.** Dispatch `task-planner` with the ticket bodies. Reconcile its waves with the
   tickets' own edges; log a ruling for each disagreement you settle. Drop the edges it lists
   under `EDGES TO DROP` unless you can name a use it missed, and take its `TIERS`
   suggestions unless the ticket says why not; log both as rulings. Its `CONTRADICTIONS`,
   `GAPS` and `RISKS` may change the models you choose or send you back to `/tickets`.
2. **Confirm once.** Show the waves with each task's tier, the critical path, the epic branch
   name, the planner's conflicts, contradictions and gaps, and that you will push that branch
   and update the tracker as tasks land. Wait for yes.
3. **Enter the epic worktree.** Create it if missing (`git fetch origin`, then
   `git worktree add .claude/worktrees/<KEY> -b <epic branch> origin/HEAD`), then
   `EnterWorktree` into it.
4. **Check the base setting:** `.claude/settings.json` must set `worktree.baseRef` to `head`,
   or agents branch from the default branch and miss earlier tasks. Stop if it's missing.
5. **Baseline.** Run setup, the full suite and lint. Log the results with the head sha. Red
   means stop: later failures can't be attributed.
6. **Start the merger.** Dispatch `epic-merger` as `<epic key>-merger` with the epic branch,
   the run id, the setup, full-suite and lint commands, the test paths, and your address. Append
   `agents: <epic key>-merger <id>` to the run log. It stops with `STARTED`; a `FAIL` means stop
   and ask. There is one merger per session: the epic branch's `git log` is its whole state, so
   a new session starts a fresh one, and otherwise only a `FAIL: environment` does (3c).

## 3. Run waves until no task is left

**a. Fill the free slots.** Ready tasks are those not done whose blockers are all done. Start
them in key order up to the parallelism limit, skipping only a task the planner listed under
`CONFLICTS` with one already running. Sharing a file is not a conflict: the merger merges
additions to one file, and a real conflict comes back as `CONFLICT` and is rebased. Don't wait
for a whole wave to close. Whenever an owner reports `DONE`, `FAILED` or `BLOCKED`, start
whatever is ready now. The waves are the plan's order, not a barrier.

**b. Dispatch one `ticket-owner` per task, in one message,** so they run in parallel. Name each
`<task key>-owner`, and append `agents: <task key>-owner <id>` to the run log. Each prompt carries: the ticket file's absolute path (not its text), the task key,
the task's tier (`small` | `standard` | `complex` from its `## Tier` section; a ticket with
none is `standard`, and one labelled `complex` is `complex`), the run id and epic branch, the
setup, named-tests, full-suite and lint commands, the config's test paths, that tier's models
and the retry model (per the config's Tiers table), any interface correction from an earlier
owner's `INTERFACES`, and your address.

From here each owner moves its ticket, proves red, gates its branch and hands it to the
merger through you; the merger merges one task at a time and gates the epic head after each
merge. You don't repeat their checks.

**c. Act on the reports.** Owners and the merger each stop with a short block. Act only on:

| Report | You |
|---|---|
| Owner `READY <KEY>` block | Relay it to the merger unchanged, with one line added: `OWNER: <the message's from address>`. Nothing else: the merger checks it and replies to the owner |
| Owner `NEEDS_RULING` | Decide it, log `Ruling: <decision> — <why> — <cost if wrong>`, and `SendMessage` the answer to the owner. If it needs the operator, it's one of the stop-and-ask cases above |
| Owner `MERGED_PENDING_RESOURCE` | Run its `RESOURCE_PROBES`, one at a time across the whole run, with the configured runner, at the merge sha — from a throwaway `git worktree add --detach`, because the merger keeps merging in the epic worktree meanwhile. Keep the output in the run log. Pass: message the owner `RESOURCE PASSED` with the output tail. Fail: message the merger `REVERT <key> <merge sha>`, wait for its `REVERTED` line, then message the owner `RESOURCE FAILED` with the output |
| Owner `DONE`, `FAILED`, `BLOCKED` | Record it, then fill the free slot (a). A failed or blocked task's dependents wait; everything else continues. A `BLOCKED` whose note is a `tracker` failure is a stop-and-ask case |
| Merger `FAIL: branch: …; holding …` | Stop and ask. Once the operator has fixed it, message the merger `CONTINUE`; the held owners are still waiting and need nothing from you |
| Merger `FAIL: environment: …; holding …` | Replace it, without asking — below |

**Replacing the merger.** The merger's only state is the epic branch's `git log`, so a fresh
one loses nothing, and every minute spent asking is a minute every held task waits. Message
the old merger `STAND DOWN` and wait for `STOOD DOWN` (or its stop). In the epic worktree,
check that the tree is clean and on the epic branch; if not, that is a `branch` problem —
stop and ask. Otherwise dispatch a new `epic-merger` as in 2.6, and append
`agents: <epic key>-merger <new id> (replaces <old id>: <its FAIL line>)` to the run log.
Then relay the held `READY` blocks to it again, in their original order; the owners are
still waiting and need nothing from you. Append an incident
(`.claude/workflow/agent-memory.md`) and tell the operator what happened, but don't wait for
an answer. Replace it once per run: a second `FAIL: environment` means something besides the
routing is wrong, and is a stop-and-ask.

Everything else — an owner's `SUBMITTED`, the merger's `MERGED` / `REJECTED` / `CONFLICT` /
`REVERTED` / `RESEND` lines — is for the log; the owner already has it and handles its own retry.

**d. Inline instead** when the whole run is one task: skip the owner and the merger, and do
every role yourself, in order, in the epic worktree (or the current branch for quoted
outcomes). Same gates, same run-log line, and the same tracker comments when there is a
tracker.

**e. Record each finished task** when its owner reports `DONE`, `FAILED` or `BLOCKED`.
1. Append one line to the run log: the key, your rulings for it, and the owner's `INTERFACES`
   and `FILES_OUTSIDE`. The owner has already appended its `<KEY>: done|failed|blocked`
   line; don't repeat it.
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
5. **Review the run.** No agent sees what a run cost as a whole: a task that waited an hour
   failed nobody. Before curation, read `progress.md` and `incidents.md` and write
   `.work/runs/<run id>/findings.md` with `Write`:
   - per task, from the stamps: dispatched → submitted → merged, and the minutes between;
     conflicts, rejections, resends and retries;
   - the merger's holds: when, why, which tasks, for how long;
   - reports that reached you late, twice, or not at all;
   - each `Ruling:` whose "cost if wrong" came true, with what it actually cost.
   Then list, under `## Findings`, each of these that happened: any merger `FAIL`, any task
   that waited more than 10 minutes on something other than its own work, the same file
   conflicting twice, a lost report, a ruling that came out wrong. Numbers from the stamps,
   not impressions. A run with none says `## Findings` / `none`.
6. **Curate the agents' memory.** Dispatch `memory-curator` as `<epic key>-memory` with the
   epic worktree's path, the epic branch, the run log's path and the paths of `findings.md`
   and `incidents.md`, and wait for its report. Agents added lessons to their memory during
   the run (`.claude/workflow/agent-memory.md`). The curator checks them across agents
   against the findings, commits the result on the epic branch, and writes what memory can't
   fix to `upstream.md`. A `BLOCKED` doesn't stop the epic: note it for the PR body.
7. **Push and open a draft PR** (`gh pr create --draft`) whose body has the epic link, a table
   of tasks (key, outcomes, merge sha), the rulings, failed or blocked tasks, what was not
   verified, the `## Findings` list from `findings.md`, and an **Agent memory** section: the
   curator's `CHANGED` lines, its `PROJECT_MD_CANDIDATES` (for the operator to add to
   `project.md` or drop), and its `UPSTREAM_FIXES`. Then have `tracker` move the epic to the
   review status and comment the PR URL.
8. **Report:** the PR URL, done / failed / blocked counts, every `Ruling:` line — those are
   the decisions you made on the operator's behalf — and, when the curator wrote
   `upstream.md`, its path and one line per section: those are proposed changes to this
   harness, for the operator to take upstream.
