---
name: addressed-dispatch
kind: practice
applies-to: orchestrator, owner
---

Every agent you dispatch gets a fixed name, its dispatch description, built from what it works
on and its type:

| Type | Name |
|---|---|
| `owner` | `<KEY>-owner` |
| `test-designer` | `<KEY>-tests` |
| `evaluator` | `<KEY>-eval` |
| `memory-curator` | `<epic key>-memory` |
| `tracker` | `<epic key>-tracker` (`<spec slug>-tracker` before the epic has a key) |
| `knowledge-scanner` | `scan-<area>` |

So `E2-T2-owner` is the owner of E2-T2, and nothing else is. A re-dispatch for the same ticket
and type reuses the name. Never invent another form, and never leave the description generic.

An agent is reachable only by the agent id its dispatch returns, so an id nobody wrote down is
an agent nobody else can message. Record every id you get back before your next step, always
beside the name:
- An owner goes in its row of the brief's ownership map (`<KEY>-owner <agent id>`), in the run
  log (`<ts> dispatch <KEY> <KEY>-owner <agent id>`) and on the board
  (`ledger.sh … --owner "<KEY>-owner <agent id>"`).
- A child (`<KEY>-tests`, `<KEY>-eval`) goes to the run's channel:
  `channel.sh post <run id> <KEY> "<KEY>-tests <agent id>"`.

When you tell the operator what you dispatched, name each agent with its id
(`<KEY>-owner <agent id>`), so they can message it from this session or from another one.
