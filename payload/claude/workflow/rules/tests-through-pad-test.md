---
name: tests-through-pad-test
kind: practice
applies-to: owner, test-designer
warrant: E3 run: agents running the runner directly bypassed the host cap, the per-test kill and the run record, and left processes running
---

Run tests only through `bash .claude/workflow/bin/pad-test.sh`: `--ids <id>...` for the ids you
are working on, `--failed` to repeat the last failures, `--tier fast` for the fast tier. The
settings deny the runner's own command (the adapter's `runner-names`), so a direct call is
refused. The wrapper caps memory and time, records the run and counts your runs against the
ticket's limit.
