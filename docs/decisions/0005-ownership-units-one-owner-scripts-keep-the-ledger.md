# 0005. Tickets are ownership units with one owner each, and scripts keep the ledger

Date: 2026-10-15 · Status: accepted (landing in steps) · Tracker: PAD redesign

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
The redesign lands in seven steps. Recorded so far:

1. **Scripts write the bookkeeping.** `merge-task.sh --run <id>` writes, once the merge is
   pushed, the evidence file and run-log line (`render-evidence.sh`), the ticket's `done` status
   and the run's `board.md` row (`ledger.sh`), and prints the PR-table row. `ledger.sh` writes
   through every adapter: local files, `gh`, and the Jira REST API with a token from the
   gitignored `.work/secrets/jira.env` (open question (b) of the brief: REST token, not a
   per-merge `tracker` dispatch). The `tracker` agent keeps reads, creates and links. A failed
   bookkeeping write prints `BOOKKEEPING FAIL` and is logged; it never fails a landed merge.
   `merge-task.sh --typecheck` adds the typecheck to the merge gate.

## Alternatives rejected
- Jira status through a `tracker` dispatch per merge: one agent and one orchestrator turn per
  task for a write a script can make.

## Consequences
The orchestrator no longer spends turns on ledger, evidence or run-log lines. A Jira project
needs each operator to create `.work/secrets/jira.env` before a run; without it every status
write is a `LEDGER FAIL`, which the run logs and the orchestrator repeats before the PR.
