---
name: addressed-dispatch
kind: practice
applies-to: orchestrator, owner
---

An agent is reachable only by the agent id its dispatch returns, so an id nobody wrote down is
an agent nobody else can message. Record every id you get back before your next step:
- An owner's id goes in its row of the brief's ownership map and in the run log
  (`<ts> dispatch <KEY> <agent id>`).
- A child's id (`<KEY>-tests`, `<KEY>-eval`) goes to the run's channel:
  `channel.sh post <run id> <KEY> "<KEY>-tests <agent id>"`.

When you tell the operator what you dispatched, name each agent with its id
(`<KEY>-owner <agent id>`), so they can message it from this session or from another one.
