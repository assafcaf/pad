---
name: dev-tests-stay-out
kind: test-authoring
applies-to: code-writer, test-designer, ticket-owner, orchestrator
check: dev-tests-stay-out.sh
---

Tests come in two tiers. Permanent tests state the ticket's outcomes, the behaviour others rely
on: the test-designer writes them in the red commit, and they merge and stay. Development tests
are scaffolding the code-writer writes while making them pass (an internal step, an
intermediate shape, a helper) under the dev path (config Commands `Dev tests`, default
`tests/_dev/`). A dev test is never committed: at the end of the task the ticket-owner promotes
each one (rewritten as an outcome test, in a follow-up red commit) or discards it, and lists the
decision in the `READY` block and the evidence. The check rejects a branch that adds a file
under the dev path or a `pytest.mark.dev` test.
