---
name: same-name-readded
kind: test-removal
applies-to: owner, orchestrator
warrant: a test moved or re-decorated under the same name looked like a removal and blocked the merge
check: same-name-readded.sh
claim: optional
---

A test removed in one place and added under the same name in the same diff was moved or
re-decorated, not deleted. It needs no REMOVALS line.
