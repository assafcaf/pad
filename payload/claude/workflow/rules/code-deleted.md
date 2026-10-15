---
name: code-deleted
kind: test-removal
applies-to: owner, orchestrator
check: code-deleted.sh
---

A deleted test file is explained when the code it tested is deleted in the same diff: every
project module the file imports (a file tracked at the base) is deleted, and at least one is.
A module that was renamed or moved does not count: its tests move with it. The check reads
Python `import` and `from ... import` lines; for another stack, add a repo rule with its own
check.

Claim it in the READY block's REMOVALS as `<file>::<test> | code-deleted | <what was deleted>`.
