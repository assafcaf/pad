---
name: append-only-sorted
kind: practice
applies-to: owner, test-designer
---

Where a shared list can't be avoided (`__all__`, a dependency list, an import block), put one
entry per line, keep the list sorted, and add your line without touching its neighbours: no
reflowing, no trailing-comma fixes, no reordering. Two tasks adding different entries then
touch different lines and merge cleanly.
