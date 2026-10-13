---
name: same-name-readded
kind: test-removal
applies-to: ticket-owner, orchestrator
check: same-name-readded.sh
claim: optional
---

A test removed in one place and added under the same name in the same diff was moved or
re-decorated, not deleted. It needs no REMOVALS line.
