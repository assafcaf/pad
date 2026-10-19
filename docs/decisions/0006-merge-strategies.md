# 0006. Merging is a named strategy, chosen dynamically by default, and every ticket still lands through merge-task.sh

Date: 2026-10-19 · Status: accepted · Tracker: E2

## Context
In Rollout-Collection's KAN-136 run on PAD 0.4.0, merging cost about ten times the
implementation. `merge-task.sh` runs the full gate once per READY ticket, one at a time, so
seven READY tickets queued for hours. A hand-run pilot merged six tickets into one candidate
and gated it once (406 s, instead of six gates of 7 to 10 minutes each). It then landed each
ticket through `merge-task.sh`, with a gate that only checked the tree matched. The pilot also
caught a real break between two tickets. Separately, the orchestrator built each long
`merge-task.sh` command by hand and got it wrong four ways. Operators want a faster default,
and a way for a repo to plug in its own merge behaviour without editing PAD.

## Decision
- **A strategy is a named file pair.** `.claude/workflow/merge-strategies/<name>.md` holds
  `name`, `script`, `description`, `options` and the guidance; `<name>.sh` is the script. PAD
  ships `single` (today's behaviour) and `batch`. A repo adds its own beside them, and
  `/pad-update` never touches a file PAD did not ship. `merge-strategies.sh validate`, which
  `preflight.sh` also runs, checks them.
- **Choosing:** the run's `merge-strategy` file (written by `/pad-run --merge`, by a mid-run
  ruling, or by the orchestrator under `dynamic`) wins, then the config's `Merge strategy:`
  line, then `dynamic`. Options are declared by the strategy and set as `<name> opt=val`.
- **`dynamic`, the default,** is a reserved setting, not a strategy. The orchestrator owns the
  run's file and starts on `batch`. Between passes it switches among the repo's strategies,
  using their "when to use" text and the signals `merge.sh --status` prints, and logs each
  switch as `STRATEGY <name> — <why>`. `merge.sh` only ever runs a concrete, validated
  strategy.
- **One entry point.** The orchestrator hands each READY ticket to
  `merge.sh --run <id> --ready <KEY> <TASK_HEAD> <RED>`. That command checks the shas, queues
  the ticket and drains the queue through the strategy under one hold of the merge lock.
- **The contract.** A strategy decides grouping, the gate and what to do on red, using
  `merge-candidate.sh` (a throwaway worktree), `merge-gate.sh` and `merge-task.sh`. A ticket
  lands only through `merge-task.sh`; with `--expect-tree` its tree must equal the one that was
  gated. After every pass the engine checks that each ticket has one result, and that every new
  commit on the epic branch is a merge it reported.
- **`batch`:** gate the candidate of up to `max` tickets once. Green, land them all. Red, land
  the longest green prefix, reject the first failing ticket and requeue the rest.
- **Adding a strategy:** `/merge-strategy` turns a prose description into the two files,
  validates them and rehearses them on a scratch repo.

## Alternatives rejected
- A strategy as a rule: rules add up and each is a check that can only fail a merge; a strategy
  is selected, one per run, and changes how merges are gated.
- A strategy as a plugin: plugins are prose an agent follows, and they add, never override.
  Merging must not depend on an agent interpreting text.
- A merge script per repo: every repo would reimplement the lock, the tree check and the
  bookkeeping, and could skip them.
- A config enum only (`single | batch`): no way for a repo to add a strategy.
- `batch` as a fixed default: it cannot back off to `single` when batches keep going red.
- A scripted chooser for `dynamic`: a repo could not extend it just by adding a strategy and
  its "when to use" text.
- The orchestrator collecting batches itself: it would build long commands and hold merge
  state, which is how KAN-136 went wrong.
- Building candidates in the epic worktree: previews would see ungated trees, and a crash would
  leave the worktree detached.

## Consequences
- Inside a batch only the final tree is gated, not the states between tickets. This is a merge
  train's contract; the epic's final full gate stays the backstop.
- `--expect-tree` depends on derived-file rebuilds being deterministic. A rebuild that isn't
  rejects a good ticket; the remedy is to fix the rebuild, or run with `single`.
- Upgraded repos choose `dynamic`, `batch` or `single` through migration 0004. Nothing
  switches silently.
- Under `dynamic`, which strategy ran is a judgment call, not a fixed setting. Every switch is
  in the run log, and the engine's checks hold whichever strategy runs.
- A custom strategy changes how fast tickets are proven, never whether: submission checks,
  protected paths, test-removal rules and bookkeeping all run in `merge-task.sh`.

## Outcome
