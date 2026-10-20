---
name: layout-as-declared
kind: repo-lint
applies-to: orchestrator
warrant: files added outside the declared layout accumulate until the declared structure no longer describes the repo
check: layout-as-declared.sh
---

Opt in by copying this file and `layout-as-declared.sh` to `.claude/workflow/rules/`, and list
the globs where files may be added, one per line, in `.claude/workflow/layout.txt` (a `*` crosses
`/`; blank lines and `#` comments are ignored). A file the diff adds that matches no glob fails
the submit. With no `layout.txt` the rule passes.
