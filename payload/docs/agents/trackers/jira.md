# Issue tracker: Jira

Issues and specs for this repo live in **Jira**, not GitHub Issues. GitHub holds the code
only — do not open, read or close issues there, and do not reach for the `gh` CLI for
issue work.

## Where

| | |
|---|---|
| Site | `https://<your-site>.atlassian.net` |
| Cloud ID | `<your-cloud-id>` |
| Project | `PROJ` — "<Your Project Name>" (team-managed software project) |
| Issue types | Epic, Feature, Story, Task, Bug, Subtask |

Issue keys look like `PROJ-12`. A bare `#12` is not a Jira reference; if a skill's wording
assumes GitHub-style `#n`, translate it to the `PROJ-n` key.

## How

Access is through the **`atlassian` MCP server** declared in `.mcp.json`. It is
project-scoped and credential-free — each person authenticates for themselves via `/mcp`
(see the README's Quick setup). If the Atlassian tools are not available in your session,
say so and stop; do not fall back to GitHub Issues.

Every tool below takes the Cloud ID above as `cloudId`.

| Operation | Tool |
|---|---|
| Create an issue | `createJiraIssue` |
| Read an issue | `getJiraIssue` |
| Find issues | `searchJiraIssuesUsingJql` |
| Comment | `addCommentToJiraIssue` |
| Edit fields, incl. labels | `editJiraIssue` |
| Move through workflow | `getTransitionsForJiraIssue`, then `transitionJiraIssue` |
| Link two issues | `getIssueLinkTypes`, then `createIssueLink` |
| Resolve a person to an account ID | `lookupJiraAccountId` |

Finding work is JQL, not a list command. The common ones:

- Open issues: `project = PROJ AND statusCategory != Done ORDER BY created DESC`
- By triage label: `project = PROJ AND labels = "needs-triage"`
- One issue's neighbours: `project = PROJ AND issue in linkedIssues("PROJ-12")`

## When a skill says "publish to the issue tracker"

Create a Jira issue in `PROJ`. Pick the issue type by size: **Task** for a discrete piece of
work (the default), **Bug** for a defect, **Story** or **Feature** for user-facing scope,
**Epic** only for something that will hold children.

## When a skill says "fetch the relevant ticket"

`getJiraIssue` on the `PROJ-n` key, with comments included. Comments carry the negotiation
that led to the ticket's current shape, and are usually where the real constraints are.

## Closing

Jira closes by **transition**, not by a close command. Call `getTransitionsForJiraIssue`
first — this is a team-managed project, so its workflow is editable and the available
transitions are not guaranteed to be the ones you remember. Then `transitionJiraIssue`.
Leave a comment saying why before transitioning.

## Pull requests

**PRs as a request surface: no.** GitHub PRs are code review for this repo, not an intake
queue. Nothing in triage reads them.

## Wayfinding operations

Used by `/wayfinder`. The **map** is one issue with **child** issues as tickets.

- **Map**: an **Epic** in `PROJ`, holding the Notes / Decisions-so-far / Fog body. Label it
  `wayfinder:map`.
- **Child ticket**: an issue whose `parent` is the map Epic — that is Jira's native
  hierarchy and it shows in the UI, so prefer it over a task list in the body. Label
  `wayfinder:<type>` (`research` / `prototype` / `grilling` / `task`). Once claimed, set
  the assignee.
- **Blocking**: a native issue link of type **Blocks** (id `10000`, `is blocked by` inward
  / `blocks` outward). For "A is blocked by B", pass `inwardIssue: B`, `outwardIssue: A`.
- **Frontier query**: the map's open children with no assignee and no open blocker —
  `project = PROJ AND parent = <map key> AND statusCategory != Done AND assignee IS EMPTY`,
  then drop any whose `is blocked by` links point at an issue that is not Done. First in
  map order wins.
- **Claim**: assign the issue to yourself. This is the session's first write.
- **Resolve**: comment the answer, transition the issue to Done, then append a context
  pointer to the map's Decisions-so-far.
