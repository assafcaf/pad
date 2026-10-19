---
name: single
script: single.sh
description: Merge each queued ticket by its own gated merge-task.sh run, one after another.
---

Use `single` when tickets are few, when they touch the same files so a batch would keep
conflicting, or when batches keep going red and each ticket should be judged alone.

Each ticket in the queue is landed by `merge-ticket.sh`, so `merge-task.sh` runs its full gate
once per ticket, in queue order, and prints `MERGED <KEY> <sha>`, `REJECTED <KEY>: ...` or
`CONFLICT <KEY>: ...`. It is the slowest strategy and the one with the fewest moving parts:
this is how PAD merged before strategies existed.
