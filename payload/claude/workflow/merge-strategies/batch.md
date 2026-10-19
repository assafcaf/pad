---
name: batch
script: batch.sh
description: Gate up to max queued tickets once as a candidate, then land them all or the longest green prefix.
options: max=8
---

Use `batch` when two or more tickets wait in the queue (`QUEUE <n>` of 2 or more in
`merge.sh --status`) and the last passes were green. The heavy serial test files set a gate's
floor, so one gate over several tickets spreads that floor: in KAN-136 one 6-ticket gate took
406 s, while single gates took 4.5 to 8.5 minutes each.

`batch` builds a candidate from the first `max` tickets (default 8) and gates its last commit
once. Green: every ticket lands through `merge-task.sh --expect-tree`, in queue order, and
prints `MERGED <KEY> <sha>`. Red: it bisects the prefixes for the longest green one (at most
1 + log2 of the batch gates), lands that prefix, prints `REJECTED <KEY>: gate failed ...` for
the first ticket after it, and `REQUEUE <KEY>` for the rest, which the next pass takes. A
conflicting ticket is reported `CONFLICT <KEY>` and left out. A known flake (`GATE FLAKE`)
requeues the whole pass and prints `FLAKE <test>`, with no bisection.

Back off to `single` after a `FLAKE` line or two red passes in a row: a batch that keeps going
red costs more gates than judging each ticket alone. Return to `batch` once the queue holds two
or more tickets again and the last merges were green.
