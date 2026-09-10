# Issue tracker: &lt;name it&gt;

A skeleton. The skills read this file to learn where issues live and how to touch them, so
every heading below has to be answered before `/dispatch` or `/evidence-dispatch` will behave.
An unanswered one is an agent guessing.

Copy the shape from `jira.md`, `github.md` or `obsidian.md` — whichever is closest to your
tracker — rather than starting from this file alone. They are worked examples of the same
contract.

**On Linear, Notion, Shortcut and friends:** they are all workable here, and none is shipped
filled in. Each is reached through an MCP server whose tool names this repo cannot verify, and
a config file that names a tool that does not exist fails at the worst moment — mid-run, in a
subagent, with a half-built branch. Run `/mcp` in Claude Code to list what your server actually
exposes, then write the real names into the "How" table below.

## Where

| | |
|---|---|
| System | |
| Workspace / project | |
| Issue keys | what one looks like, e.g. `ENG-12`. Skills that write `PROJ-12` mean this. |
| Access | MCP server name, CLI, or API — and what authenticates it |

## How

Name the actual tool or command for each. "The MCP server" is not an answer.

| Operation | Tool |
|---|---|
| Create an issue | |
| Read an issue, with comments | |
| Find issues | |
| Comment | |
| Edit fields, incl. labels | |
| Move through workflow | |
| Link two issues | |
| Resolve a person to an id | |

## When a skill says "publish to the issue tracker"

Which issue type, and how size maps to it.

## When a skill says "fetch the relevant ticket"

How to read one **with its comments**. The comments carry the negotiation that led to the
ticket's current shape and are usually where the real constraints are; a config that fetches
only the body loses that silently.

## Closing

Whether closing is a state change, a transition, or a command — and whether the reason goes in
a comment first. Say which, because agents will otherwise pick the one their training suggests.

## Pull requests

Whether PRs are an intake surface. Unless you say otherwise the skills assume **no** — PRs are
code review, and triage does not read them.

## Wayfinding operations

Only needed if you use `/wayfinder`. Define:

- **Map** — the container issue holding Notes / Decisions-so-far / Fog, and how it is marked.
- **Child ticket** — how a ticket points at its map. Prefer your tracker's native parent field
  over a convention in the body; fall back to a convention only if there is none.
- **Blocking** — the native link type, or the body convention that stands in for one.
- **Frontier query** — open children of the map, unassigned, with no unresolved blocker.
  Write the literal query.
- **Claim** — how a session takes a ticket. This is its first write.
- **Resolve** — comment the answer, close, append a pointer to the map's Decisions-so-far.
