---
name: no-pinned-aggregates
kind: test-authoring
applies-to: test-designer, owner, task-planner
---

No test pins a number that every task changes: a suite's test count in the README, the number
of registered modules, a total line count. Each task that touches it edits the same line, so
every merge after the first conflicts (KAN-107: 9 of 9 later merges). Assert the property
instead (the README names the command that counts the suite), or list the file in the config's
Derived files so merges rebuild it. The planner flags such a line as a hotspot.
