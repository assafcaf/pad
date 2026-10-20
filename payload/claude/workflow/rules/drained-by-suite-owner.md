---
name: drained-by-suite-owner
kind: test-removal
applies-to: owner, orchestrator
check: drained-by-suite-owner.sh
claim: optional
warrant: docs/decisions/0007-test-regime.md - an acceptance test leaves the suite only through the suite owner's verdict (handoff U3)
---

A removed acceptance test is explained when the removing ticket is a suite ticket (its commit
subject is `suite(<KEY>): ...`) and a line `VERDICT <KEY> <id> promote|rewrite|retire <tier> —
<why>` in a commit message of the range names the test. Any other ticket that removes a test
needs one of the other test-removal rules.
