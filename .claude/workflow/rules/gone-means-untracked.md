---
name: gone-means-untracked
kind: test-authoring
applies-to: test-designer, owner
check: gone-means-untracked.sh
---

A test that something was removed from the repo asks git, not the disk: `git ls-files <path>`
is empty. `Path.exists()` sees gitignored leftovers such as `__pycache__/` and fails on a
machine where the old code once ran (KAN-126). The check rejects an added
`assert not <...>.exists()` in a test file.
