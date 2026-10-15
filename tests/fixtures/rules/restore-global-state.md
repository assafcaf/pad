---
name: restore-global-state
kind: practice
applies-to: owner
---

A repo-defined rule, the example from Rollout-Collection's KAN-107: code that changes
process-global state (environment variables, global RNG seeds, library-wide flags such as
torch's deterministic mode) restores it before it returns, or does the change inside a context
manager that does. A leak makes tests order-dependent, which shows up only under xdist or a
shuffled order.
