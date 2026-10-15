---
name: pad-run
description: Run an epic's tickets to merged code. One owner per ticket works in its own worktree from start to merged; the orchestrator writes the run's brief, dispatches, lands each READY with merge-task.sh, reviews every wave with the operator, replans, and finishes with a PR. Scripts keep the ledger. Run as /pad-run <epic key | task keys | plan path | outcomes>.
argument-hint: "<epic key | task keys… | plan path | outcomes in quotes> [--gate full|affected]"
disable-model-invocation: true
---

# Tickets → merged code

Input: `$ARGUMENTS`. Read `.claude/workflow/config.md` and
`.claude/workflow/definition-of-done.md`.
Run `bash .claude/workflow/bin/rules.sh for orchestrator` and follow every rule it prints
(`.claude/workflow/rules/`).

`--gate full|affected` picks what each merge's gate runs; without it, the config's Execution →
Gate. With `affected`, every `merge-task.sh` call adds `--affected "<named tests>"` (the config's
Run named tests command, `{tests}` left in). With the config's Test workers set, every call adds
`--workers <n>`.

You govern the pipeline, not the conversations. Your verbs are partition, sequence, land,
replan and escalate. You never write product code, and you never carry a message between two
agents: owners talk to each other directly and through the run's channel.

| Agent | Does | Dispatched by |
|---|---|---|
| `owner` | One ticket from start to merged: its tests (unless protected), its code, its gates, its rebase | You, one per ticket |
| `test-designer` | A protected ticket's failing tests + stubs, committed red | Its owner, as a blocking child |
| `evaluator` | A fresh-context verdict on a visual ticket's render against its reference | Its owner |
| `tracker` | Tracker reads, ticket creation and links | You and `/tickets` only. Status and comment writes go through `ledger.sh`, for every adapter |
| `memory-curator` | Keeps the agents' persistent memory clean: keeps, tightens, merges or deletes lessons, never adds them | You, once, at the end of the epic |

You pay per hand-off, not per work: every turn you take re-reads your whole context. So a
ticket costs you one dispatch, one background merge per `READY`, and nothing in between.
Structure lives in scripts and files, not in your turns.

**Names and addresses.** Give every dispatch a description that names what it works on:
`<task key>-owner`. Owners name their test-designer `<task key>-tests`. The name is for people
reading logs; messages are routed by the agent id each dispatch returns, so record every
owner's id in the brief's roster, and reply to a message at its `from` address.

**Wait for notifications; never poll.** An agent's report arrives on its own when it stops.
A `sleep`, an `echo`, or a status check while you wait re-reads your whole context for nothing.

**Keep going without check-ins.** After the start confirmation, don't pause between tickets.
When the scope and the tickets don't settle something, decide it, append it to the brief's
`## Rulings` and log `Ruling: <decision> — <why> — <cost if wrong>`. Only these need the
operator, as a question:
- an irreversible action outside this flow
- a security-sensitive action
- changing shared state other than the epic branch and its tickets (`main`, a serial
  resource's current state, other tickets)
- a baseline that is already red
- a change of scope (the scope is frozen; that is a new `/spec`)

**A question parks one ticket, not the run.** Send the operator a push notification with the
ticket key and the question, and append it to the run log as `QUESTION <KEY>: <question>` with
`bash .claude/workflow/bin/run-log.sh <run id> "QUESTION <KEY>: <question>"`. Then park only
that ticket: its owner waits for your answer, and its dependents wait with it. A question that
belongs to no one ticket (a red baseline) uses the epic key. Never call `AskUserQuestion` for a
question: it blocks the whole session until someone answers. A `NEEDS_RULING` the brief can't
answer and you shouldn't is parked the same way, for the next review gate: nobody guesses.

**Everything else keeps moving while a ticket is parked.** Keep dispatching ready tickets and
running `merge-task.sh` for each `READY`. The operator answers by typing into this session:
append the answer to the brief's `## Rulings`, `SendMessage` it to the parked owner, which
resumes from where it stopped, and fill any slot its dependents open.

**Pause only when nothing is runnable.** When every ticket left is parked, failed or waiting on
one of those, and no owner or merge is in flight, pause the run: send one more push notification
saying the run is paused and which questions hold it, append `PAUSED: <keys>` to the run log,
and end your turn. The next answer resumes the run.

**Log every halt with `halt-log.sh`.** When you park a ticket, and when you pause the run, run
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

| Input | Tickets |
|---|---|
| Epic key | `tracker` `read-epic`, then `read-task` for each child that isn't done |
| Task keys | Those tickets, plus any unfinished ones they depend on (ask before pulling in extras) |
| Plan path | The plan file's tickets and their recorded keys |
| Outcomes in quotes | One ticket, no tracker. Run it inline (3d) on the current branch, after asking: current branch, or a worktree? |

The run id is the epic key or a slug. **The run's files** live in `.work/runs/<run id>/` in the
main checkout (the parent of `git rev-parse --git-common-dir`), the same from every worktree:

| File | Holds | Written by |
|---|---|---|
| `scope.md` | The approved spec: intent, non-goals, references, protected paths, domains. Frozen | `/tickets` |
| `brief.md` | What every owner reads on start (section 2) | You; you append `## Rulings` |
| `board.md` | One row per ticket: key, owner, status, branch, sha, evidence | Scripts only (`ledger.sh --run`) |
| `channel.md` | Owners' interface decisions, renames in shared files, discoveries, questions to peers | Owners, through `channel.sh post` |
| `progress.md` | The run log: events, rulings, questions, removals | Scripts and you, through `run-log.sh` |
| `tickets/<KEY>.md` | Each ticket body | You, once |

**Write each ticket body once,** to `.work/runs/<run id>/tickets/<KEY>.md`, with `Write`, as
`tracker` returned it. From here every agent gets the file's absolute path and reads it, never
the body as text.

**Resuming in a new session.** The earlier session's agents are gone; the files and git are
not. Read `scope.md`, `brief.md`, `board.md` and `channel.md`, the run log's events and
`git log` on the epic branch, and continue. A ticket whose
`Merge <KEY>` commit is on the epic branch is merged: if `board.md` doesn't say `done`, record
it with `ledger.sh <KEY> status done "<comment>" --run <run id> --sha <sha7>`. A ticket doing
with no merge starts over with a new owner, who picks it up from the ticket, the brief, the
channel and its branch if one was pushed; remove its earlier worktree (`git worktree list`).
Ownership belongs to the ticket, not the agent: the seat is the same with a new occupant.

**After compaction in the same session,** the agents are still running: restart nothing. The
brief's roster gives you back each owner's id; trust the run files and `git log` over your
memory.

## 2. Start

1. **Plan.** Run `bash .claude/workflow/bin/plan-check.sh .work/runs/<run id>/tickets`. Its
   `OVERLAPS`, `PROTECTED` and `DEPENDS` lines are planning errors: send them back to
   `/tickets`. Waves follow the tickets' `Depends on`; the script prints the `CRITICAL-PATH`,
   and its `HOTSPOTS` and `SWEEPS` are worth a ruling each.
2. **Confirm once.** Show the waves with each ticket's reference and Protected flag, the
   critical path, the hotspots, the epic branch name, and that you will push that branch and
   update the tracker as tickets land. Wait for yes.
3. **Enter the epic worktree.** Create it if missing (`git fetch origin`, then
   `git worktree add .claude/worktrees/<KEY> -b <epic branch> origin/HEAD`). Never call
   `EnterWorktree`: it moves your session and strands the agents you resume. Reach the epic
   worktree with `git -C .claude/worktrees/<KEY> <command>`.
4. **Check the base setting:** `.claude/settings.json` must set `worktree.baseRef` to `head`,
   or agents branch from the default branch and miss earlier merges. Stop if it's missing. Even
   when set, `head` is the orchestrator's head: if you don't sit in the epic worktree it
   resolves to the default branch, so owners check their base (owner.md, Procedure step 1).
5. **Baseline.** Run setup, then `bash .claude/workflow/bin/preflight.sh` in the epic worktree.
   It proves the setup still holds: git moves and every unattended command allowed, knowledge
   paths resolve, config sections match the PAD version, dependency directory, agent models,
   executable scripts, `.gitignore`, and a render check when a surface has a Render command. On
   `PREFLIGHT FAILED <n>`, stop before any wave and show the operator its `PREFLIGHT FAIL`
   lines (an old PAD version names `/setup-workflow upgrade`). Then run the full suite and
   lint. Log the results with the head sha. Red means stop: later failures can't be
   attributed. Once green, start each configured preview with
   `bash .claude/workflow/bin/preview.sh start --surface <name> --worktree <epic worktree>` (a
   surface with no `Preview start` is a no-op), so each merge shows up live for the operator.
   Don't restart it yourself: `merge-task.sh` stops a running preview before setup and starts
   it again whenever a merge touches the surface's `Restart when changed` paths.
6. **Write the brief.** Fill `.claude/workflow/brief-template.md` into
   `.work/runs/<run id>/brief.md` with `Write`: links to the scope, the references and the
   decision record; the system already in the code that owners must reuse; the rule names
   `rules.sh for owner` prints; the gates; the ownership map from the tickets' `Owns`,
   `Touches` and `Protected`; the protocol. Link, never paraphrase: about 60 lines at most.
   Read every plugin the config's `## Plugins` table lists with `Extends` `pad-run`
   (`.claude/workflow/plugins.md`) and carry out the steps it adds where it says, and link in
   the brief each plugin that extends `owner`.

## 3. Run waves until no ticket is left

**a. Fill the free slots.** Ready tickets are those not done whose `Depends on` are all merged.
Start them all in key order, or up to the config's parallelism cap if it sets one. Tickets own
disjoint files and add only to shared ones, so they run side by side; a real conflict comes
back as `CONFLICT` and the owner rebases. Don't wait for a whole wave to close: whenever a
ticket merges, start whatever is ready now. The waves are the plan's order, not a barrier.

**b. Dispatch one `owner` per ticket, in one message,** so they run in parallel. Each prompt
carries only the ticket file's absolute path and the brief's: the commands, gates, rules and
team are in the brief. Name each `<task key>-owner`. Then, for each, fill its agent id into the
brief's ownership map, append `<ts> dispatch <KEY> <agent id>` to the run log (`ts` from
`date -u +%Y-%m-%dT%H:%M:%SZ`), and mark it doing:
`bash .claude/workflow/bin/ledger.sh <KEY> status doing "<run id>, <epic branch>" --run <run id> --owner <agent id>`
from the epic worktree.

From here each owner writes, proves red, gates, submits and rebases its own branch, and
reports one line. You land it with `merge-task.sh`, which takes the merge lock, so tickets
merge one at a time, each gated on the head the one before produced. You don't repeat the
owner's checks, and you don't review its test removals: `merge-task.sh` runs
`weakened-tests.sh`, which passes a removal only when a rule explains it.

**c. Act on the reports.** Each owner report is one line; each `merge-task.sh` run ends with
one last line. Never read diffs, logs or merge output into your context: act only on:

| Report | You |
|---|---|
| Owner `READY <KEY> <TASK_HEAD> <RED>` | Run `bash .claude/workflow/bin/merge-task.sh --worktree <epic worktree> --branch <epic branch> --setup "<setup>" --gate "<full suite>" --typecheck "<typecheck>" --lint "<lint>" --test-paths "<test paths>" [--derived "<path>=<cmd>" …] --protected "<the config's Protected paths>" --ticket <ticket file> --run <run id> --outcomes "<O ids or ->" <KEY> <RED> <TASK_HEAD> "<the ticket's title>"`, one `--derived` per row of the config's Derived files, and, for a ticket whose reference is a mock crop on a surface with a Render command, `--capture "bash .claude/workflow/bin/render-check.sh --surface <surface> --route <route> --viewport <WxH> --out {out}"`, in the background (`run_in_background`), and end your turn. That is the whole hand-off: one turn |
| `merge-task.sh` `MERGED <sha>` | Nothing to write: the script recorded it (3e). If the owner's report listed `RESOURCE_PROBES`, run them (below). Fill the free slot (a) |
| `merge-task.sh` `CONFLICT …` or `REJECTED …` | `SendMessage` the owner that line unchanged. It rebases or fixes, re-gates and reports `READY` again |
| `merge-task.sh` `REJECTED` whose failing tests all sit in files the ticket didn't touch and doesn't import | A false positive: the script already reran them once. Rerun `merge-task.sh` once in the background with the same `RED` and `TASK_HEAD`; the owner hears only the rerun's last line |
| `merge-task.sh` exit 2 (`ERROR <KEY>: …`) | Infrastructure, not the ticket. Run it once more, from a fresh start in the background; when the error says the merge is committed locally, the fresh start is the config's `push-epic` move instead. A second `ERROR` is a question (above): park that ticket |
| Owner `NEEDS_RULING <KEY> <question>` | Answer from the scope and the brief, append the answer to the brief's `## Rulings`, log `Ruling: <decision> — <why> — <cost if wrong>`, and `SendMessage` it to the owner. If it needs the operator, it's a question (above): park the ticket |
| Owner `FAILED <KEY> <why>` | Record it (3e). Its dependents wait; everything else continues. **Stall rule:** a ticket that fails twice is replanned (3g), never re-dispatched as it is |

**Resource probes.** After `MERGED`, run the owner's `RESOURCE_PROBES` one at a time across the
whole run, with the configured runner, at the merge sha, from a throwaway
`git worktree add --detach`. Keep the output in the run log. On a failure, once no
`merge-task.sh` is running, revert that merge in the epic worktree with the `revert-merge` move
(`config.md`, `## Git moves`), run the full suite and lint there, push with `push-epic`, and
send the owner `RESOURCE FAILED` with the output tail: it fixes and reports `READY` again. A
serial-resource failure is the only reason a merge is ever reverted.

A flake that forces reruns is fixed at its cause (`.claude/workflow/testing.md`, "Pass under
load"), not rerun again.

**d. Inline instead** when the whole run is one ticket: skip the owner, and do its procedure
yourself (`.claude/agents/owner.md`), landing it with `merge-task.sh`, in the epic worktree (or
the current branch for quoted outcomes). Same gates, same bookkeeping.

**e. Record each finished ticket.** A merged ticket is already recorded: the
`merge-task.sh --run` that merged it wrote its evidence file, its run-log event and line, the
ticket's `done` status and its `board.md` row, and printed its PR-table row. Write none of
those again. A `BOOKKEEPING FAIL` line in that merge's output is a write to make again before
the PR (step 4). For `FAILED`, run `ledger.sh <KEY> comment "<the owner's reason>" --run <run id>`
and leave the status at `doing`. `ledger.sh` writes through the configured adapter: local
files, `gh`, or the Jira REST API (`.claude/workflow/trackers/<adapter>.md`). A `LEDGER FAIL`
never stops the run: log the write it missed with `run-log.sh`, carry on, and make the missed
writes again before you open the PR (step 4).

**f. Review every wave.** Read `Cadence` under `## Review` in the config: `per-wave` (the
default), `after-first-wave`, `end-only` or `none`. At each checkpoint it names, run
`bash .claude/workflow/bin/review.sh --run <run id>`: it writes `review-<n>.md` and `.html`
from the board and the evidence (merged keys and shas, render pairs side by side, evidence
lines, what is unverified). Send the operator a push notification that the packet is ready,
the same way as a parked question; the run doesn't stop while the operator reads. Then read
`channel.md` since the last checkpoint (`channel.sh read <run id> --since <ts>`): a decision
there that binds other tickets becomes a ruling in the brief. Parked `NEEDS_RULING`s go to the
operator now.

**g. Replan.** The decomposition is planned wave by wave. After each review, and whenever the
stall rule fires: the operator's free-text feedback, a split of a twice-failed ticket, and the
next wave's tickets all become **new tickets**, written through `/tickets`' sections 1 and 2
(its lint, `plan-check.sh`, included) and shown to the operator before they are published. A
merged ticket is never reopened: a fix is a new ticket that depends on it.

## 4. Finish the epic

Once every owner has reported and no `merge-task.sh` is running, you may commit and push on the
epic branch yourself. Final-review fixes (step 2) land through `merge-task.sh` like any ticket,
so refresh the knowledge layer and write the development record after they land.

1. **Full gates** at the epic head, even under `gate=affected`: the full suite and lint, then
   `bash .claude/workflow/bin/surface-checks.sh`: any `SURFACES FAIL <surface>` line fails the
   gate. Then stop each preview started at the baseline with
   `bash .claude/workflow/bin/preview.sh stop --surface <name> --worktree <epic worktree>`, so
   it holds no file in the worktree.
2. **Final review.** If config sets a level, run `/code-review <level>`; fix only correctness
   findings, test-first: one new ticket and one `owner` per fix, landed by `merge-task.sh`. In
   an inline run, fix them inline.
3. **Knowledge refresh.** Only when the config's `## Project knowledge` section is `Mode: on`.
   Run `/knowledge-layer refresh` against the epic head. Approve its cited lines (terms,
   modules, paths, overlaps) as a ruling; What this repo is, Invariants and Pitfalls stay as
   they are. A doubt about them, or a blocker whose answer was already an Invariant, goes in
   the PR body for the operator. Commit the result on the epic branch. Do not edit those
   files yourself: a line the operator did not write is the kind that measures worse than no
   line at all.
4. **Development record.** Append an Outcome section to the epic's `docs/decisions/` entry, or
   create one per `docs/decisions/README.md`: what was built, where it departed from the scope,
   and why. Use `Edit` to append and `Write` to create, not a heredoc
   (`.claude/workflow/writing-files.md`). Commit it.
5. **Curate the agents' memory.** Dispatch `memory-curator` as `<epic key>-memory` with the
   epic worktree's path, the epic branch, the run log's path and the channel's, and wait for
   its report. Agents added lessons to their memory during the run
   (`.claude/workflow/agent-memory.md`). The curator keeps, tightens, merges or deletes them,
   and commits the result on the epic branch. A `BLOCKED` doesn't stop the epic: note it for
   the PR body.
6. **Measure the run.** `bash .claude/workflow/bin/run-stats.sh --run <run id>` prints the
   run's tickets, per-ticket wall time, conflicts, rejections, rework rounds, replans and the
   longest ticket. Its `STAT` lines go in the PR body.
7. **Push and open a draft PR** (`gh pr create --draft`) whose body has the epic link, a table
   of tickets (key, outcomes, merge sha), the rulings, failed tickets, what was not verified,
   a **Test removals** section (every `REMOVALS <KEY>:` line `merge-task.sh` logged: the test
   and the rule that explains it), the run's `STAT` lines, and an **Agent memory** section: the
   curator's `CHANGED` lines, its `PROJECT_MD_CANDIDATES` (for the operator to add to
   `project.md` or drop), its `UPSTREAM_FIXES`, its `LOCAL_CANDIDATES` (for `CLAUDE.local.md`)
   and its `REPEATED_RULINGS` (questions for the next `/tickets`), each group listed
   separately. Then have `tracker` move the epic to the review status and comment the PR URL.
   Stop the local app if you started one.
8. **Report:** the PR URL, merged / failed counts, and every `Ruling:` line — those are the
   decisions you made on the operator's behalf.

## 5. After the PR merges: clean up

The operator merges the PR, never you. When they tell you it has merged (or a later
`/pad-run` finds a finished run whose PR has merged), leave nothing behind:
`bash .claude/workflow/bin/cleanup-run.sh --run <run id> --epic-branch <epic branch>`, run from
the main checkout. It refuses unless the epic is merged (an ancestor of the default branch, or
`gh` says the PR is `MERGED`, for a squash merge), then removes the run's worktrees, the
epic's and the owners' local branches, the epic's remote branch, stale merge locks and preview
pid files, and the run's directory under `.work/runs/`; `.work/tickets/` stays as the ledger.
It never removes a worktree with uncommitted changes: each `SKIP` line is one for the operator
to look at. Report its last line.
