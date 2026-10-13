---
name: no-full-suite-in-agents
kind: practice
applies-to: code-writer, test-designer, ticket-owner
---

Agents run the task's named tests, the typecheck and lint, never the full suite. The full suite
runs in `merge-task.sh`'s gate, once per merge, on the merged tree. Ten parallel tasks each
running a four-minute suite on one host pushed every gate to 36 minutes or more (KAN-107). A
break in another task's tests then shows at merge as `REJECTED`, which is the cheaper place.
