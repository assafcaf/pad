---
name: read-channel-first
kind: practice
applies-to: owner, test-designer
---

Read the run's channel before you write anything and again before every rebase:
`bash .claude/workflow/bin/channel.sh read <run id>` (`--since <ts>` for what is new). Peers
post their interface decisions, renames in shared files and discoveries there; building
against a name a peer already changed is a conflict you could have avoided. When you settle an
interface, change a shared file or find something the team will need, post one line with its
path: `channel.sh post <run id> <KEY> "<line>"`.
