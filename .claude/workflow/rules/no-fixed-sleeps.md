---
name: no-fixed-sleeps
kind: test-authoring
applies-to: test-designer, owner
check: no-fixed-sleeps.sh
---

A test never waits a fixed time for something to happen: under the load of several suites at
once, any fixed wait is too short (KAN-107: a `sleep(2.0)` failed under xdist and rejected a
merge twice). Poll for the condition with a deadline sized for load, sleeping briefly between
polls. The check rejects an added `sleep(<n>)` of 0.5 s or more in a test file.
