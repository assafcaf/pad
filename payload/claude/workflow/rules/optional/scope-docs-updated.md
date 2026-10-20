---
name: scope-docs-updated
kind: repo-lint
applies-to: orchestrator
warrant: a change to the product that leaves every document untouched lets the written scope drift from the code
check: scope-docs-updated.sh
---

Opt in by copying this file and `scope-docs-updated.sh` to `.claude/workflow/rules/`. A diff that
changes anything outside the test paths and the documents must also change at least one Markdown
file (the ticket's scope, a decision record, a README). Change only tests or only documents and
the rule has nothing to say. The check runs at `task-submit.sh`, over the whole diff.
