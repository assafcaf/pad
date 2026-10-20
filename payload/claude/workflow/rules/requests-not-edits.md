---
name: requests-not-edits
kind: practice
applies-to: owner
warrant: an edit outside a ticket file list is thrown away at merge, after the work is done
---

You write only the files your ticket owns (`## Owns`) and add only to the shared files it
touches (`## Touches`). A change anywhere else is a request to that file's owner: send it by
`SendMessage` to the owner the brief's ownership map names, or post it to the run's channel,
and build against what it agrees. `task-submit.sh --ticket` rejects a branch whose diff leaves
the ticket's files, so an edit you make there is thrown away at merge. If the file's ticket has
no owner yet, that is a `NEEDS_RULING`: the orchestrator assigns it.
