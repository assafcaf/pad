---
name: ported-from
kind: test-removal
applies-to: test-designer, owner, orchestrator
check: ported-from.sh
---

A test rewritten against a new interface keeps its history: put
`# ported-from: <old file>::<old test name>` on a line of the new test (a comment above its
`def` is the usual place), one line per old test it replaces. The old test's removal is then
explained. Claim it as `<old file>::<old test> | ported-from | <new test id>`.
