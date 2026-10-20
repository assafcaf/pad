---
name: platform-neutral
kind: test-authoring
applies-to: test-designer, owner
warrant: KAN-119: a POSIX-only kill test skipped on Windows left the behaviour untested there
check: platform-neutral.sh
---

A test runs on every platform the suite runs on; never skip one by platform. When the behavior
is a platform's (a POSIX process-group kill), test what a caller observes through a path every
platform has: start a child process, kill it (`Popen.kill()`, or `os._exit` in the child), and
assert the state it leaves. KAN-119 did this for a kill/resume test. The real platform path
then goes unexercised by the suite; say so in the task's evidence.
