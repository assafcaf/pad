---
name: register-by-file
kind: practice
applies-to: owner, test-designer
warrant: a hand-edited central list made every task that added an entry conflict on the same lines
---

A new entry (a command, a plugin, a task family, a route) goes in a file of its own that the
code finds by discovery: a directory scan, `pkgutil.iter_modules`, entry points. Sort what
discovery returns so the order is stable. A hand-edited central list makes every task that adds
an entry edit the same lines, and every merge after the first conflict.
