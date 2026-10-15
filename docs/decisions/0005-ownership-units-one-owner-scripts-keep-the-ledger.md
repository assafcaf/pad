# 0005. Tickets are ownership units with one owner each, and scripts keep the ledger

Date: 2026-10-15 · Status: accepted · Tracker: PAD 0.4.0 redesign

Supersedes the ticket-owner / test-designer / code-writer layering of 0001 and "the orchestrator
is the only ledger writer" of 0002.

## Context
PAD 0.2.0 ran WorkoutTracker's E17 (a UI redesign, 11 tasks) through spec → tickets →
test-designer → code-writer, with a ticket-owner per task relaying between them and the
orchestrator. Every gate passed and the result did not look like the mock. A light rebuild (one
62-line brief, one agent per screen with the mock as its spec, build → render → compare → fix)
matched it in the same wall clock, with ~118 → ~30 orchestrator turns. The retrospective and an
outside-evidence review agree: each hand-off loses intent; two writers inside one task and
tickets split by concern cause conflicts; done must be judged against the real goal by someone
other than the writer; and the orchestrator pays per hand-off, so bookkeeping routed through it
is its main cost.

## Decision
The redesign landed in seven steps, all in PAD 0.4.0:

1. **Scripts write the bookkeeping.** `merge-task.sh --run <id>` writes, once the merge is
   pushed, the evidence file and run-log line (`render-evidence.sh`), the ticket's `done` status
   and the run's `board.md` row (`ledger.sh`), and prints the PR-table row. `ledger.sh` writes
   through every adapter: local files, `gh`, and the Jira REST API with a token from the
   gitignored `.work/secrets/jira.env` (open question (b) of the brief: REST token, not a
   per-merge `tracker` dispatch). The `tracker` agent keeps reads, creates and links. A failed
   bookkeeping write prints `BOOKKEEPING FAIL` and is logged; it never fails a landed merge.
   `merge-task.sh --typecheck` adds the typecheck to the merge gate.

2. **One owner per ticket.** `owner` replaces `ticket-owner` and `code-writer`: it writes the
   code, and the tests unless the ticket needs the strict discipline, in which case a
   `test-designer` writes them as a blocking child and they are read-only to the owner. It
   gates (named tests, typecheck, lint), runs `task-submit.sh`, rebases onto the epic head and
   reports one line: `READY <KEY> <head> <red>`, `FAILED` or `NEEDS_RULING`. The orchestrator
   lands a `READY` with one background `merge-task.sh` and sends the owner only a `CONFLICT` or
   `REJECTED` line, which the owner fixes and re-reports. The orchestrator's removal review is
   gone: `weakened-tests.sh` passes a removal only when a rule explains it, and `merge-task.sh`
   logs each explained removal for the PR. `epic-merger`, `gate-runner`, the `pad-task`
   workflow and `--mode workflow` are deleted. Models are one Agents-table column per agent;
   until step 3 the tier only decides the strict discipline.

3. **Tickets are ownership units.** A ticket is valid only if it is ownable (disjoint `Owns`,
   append-only `Touches`), checkable (it names its reference, or it is a spike that produces
   one and no product code), finishable by one owner, and owned start to merged. `/tickets`
   splits by surface or module, never by concern, and lints the plan with `plan-check.sh`
   (overlaps, hotspots, protected mismatches, the critical path, sweeps) before the operator
   sees it; `task-planner` is retired. `task-submit.sh --ticket` rejects a write outside the
   ticket's files. Tiers are gone: ceremony follows what the diff touches. A ticket whose files
   match the config's `## Protected paths` takes the strict discipline, and
   `merge-task.sh --protected` rejects a protected diff whose red commit has no
   `PAD-Role: test-designer` trailer (a guard against honest mistakes, not against a forger).
4. **The spec is the scope; done is per reference class.** `/spec` names a reference per area
   (or a spike), the protected paths and the domains, and writes outcomes only where tests are
   the reference; `/tickets` copies it to the run's `scope.md`. `definition-of-done.md` judges
   each reference class — visual, contract tests, behaviour tests, reproduction, golden or
   metric, human — by someone other than the writer.

5. **`/pad-run` governs from files.** The run's state is four files in `.work/runs/<epic>/` —
   `scope.md` (frozen), `brief.md` (links, the system already in the code, gates, the
   ownership map and roster, the protocol, appended rulings), `board.md` (scripts only) and
   `channel.md` (owners' posts) — plus git, so a killed run resumes from them. An owner is
   dispatched with two paths, the ticket and the brief. Every wave ends with a `review.sh`
   packet; the operator's feedback, a twice-failed ticket's split and the next wave all become
   new tickets through `/tickets`' lint. After the PR merges, `cleanup-run.sh` removes the
   run's worktrees, branches, locks and run directory, so nothing piles up locally.
6. **Visual references get an independent judge.** A Surfaces row with a Render command gives
   a visual class: the owner renders with `render-check.sh`, compares, and an `evaluator` with
   a fresh context returns the verdict; `merge-task.sh --capture` renders the merged tree into
   the evidence. A repo with no render command has no visual class: nothing assumes a web app.
7. **Measured, not estimated.** `merge-task.sh` logs each result and the orchestrator each
   dispatch as timestamped events; `run-stats.sh` turns them into tickets, wall time,
   conflicts, rejections, rework rounds and replans for the PR body. The shape should become
   the default only after one data-heavy, non-UI epic has run on it and been measured.

Open questions from the brief, as settled:
- (a) The owner's rebase uses `git rebase <sha>`, the form `rebase-red` already needed, under
  its own capability `rebase-onto-epic-head`, so `check-moves.sh` proves it is allowed. Whether
  the permission classifier lets the rebase-and-resubmit loop run unattended is confirmed only
  by a live run; the first one should watch for it.
- (b) Jira status writes use the REST token (step 1).
- (c) The orchestrator skill becomes `/pad-run`, not `/run`: Claude Code ships a built-in `run`
  skill, and the `pad-` prefix matches `/pad-update`. `/batch-implement` stays one version as
  an alias.

## Alternatives rejected
- Jira status through a `tracker` dispatch per merge: one agent and one orchestrator turn per
  task for a write a script can make.
- Keeping a ticket-owner over a test-designer and a code-writer: a relay by design. Every
  objection, red sha and merge result crossed it, and the code-writer never saw the reference.
- Owners driving their own merges against the epic worktree: E8 broke that way. Merges stay
  orchestrator-run, one background script per `READY`.

## Consequences
The orchestrator no longer spends turns on ledger, evidence or run-log lines. A Jira project
needs each operator to create `.work/secrets/jira.env` before a run; without it every status
write is a `LEDGER FAIL`, which the run logs and the orchestrator repeats before the PR.
