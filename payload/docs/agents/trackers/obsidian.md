# Issue tracker: an Obsidian vault

Issues and specs for this repo live as **Markdown notes in an Obsidian vault**. There is no
API and no server: an agent reads and writes files, and Obsidian renders them.

Obsidian imposes no issue model, so the convention below *is* the tracker. It is chosen to be
plain enough that `grep` is a query engine and Obsidian's own graph, backlinks and Dataview
all work on it without plugins beyond Dataview. Change it if you like — but change it here,
because this file is what every agent reads.

## Where

| | |
|---|---|
| Vault | `<absolute path to the vault>` |
| Issue folder | `<vault>/issues/` |
| Issue file | `issues/PROJ-12.md` — the key is the filename |
| Next key | the highest existing `PROJ-n` plus one. Never reuse a key. |

The vault may be outside the repo. If it is, an agent needs the absolute path — it cannot
guess it, and a relative one breaks the moment a run happens in a worktree.

## The note format

Frontmatter is the queryable part. Keep it flat; Dataview and `grep` both cope badly with
nesting.

```markdown
---
key: PROJ-12
type: task          # task | bug | feature | epic
status: open        # open | in-progress | blocked | done
labels: [architect]
assignee:           # empty until claimed
parent:             # [[PROJ-4]] for a child of an epic or a wayfinder map
blocked-by: []      # [[PROJ-9]] — wikilinks, so backlinks work
created: 2026-01-01
---

# PROJ-12 — <one-line title>

<body>

## Log

- 2026-01-01 — <what happened, and why>
```

## How

| Operation | Mechanism |
|---|---|
| Create an issue | write `issues/<next key>.md` with the frontmatter above |
| Read an issue | read the file, **including its `## Log`** |
| Find issues | `grep -l 'status: open' issues/*.md`, or Dataview in Obsidian |
| Comment | append a dated bullet under `## Log` — never edit an older one |
| Edit fields, incl. labels | edit the frontmatter |
| Move through workflow | set `status:` |
| Link two issues | a `[[PROJ-n]]` wikilink; put blockers in `blocked-by` |
| Resolve a person | there are no accounts — `assignee:` is free text |

Append to `## Log`, never rewrite it. It is the comment thread, and the reason a decision was
made is worth more than a tidy file.

## When a skill says "publish to the issue tracker"

Write a new note in `issues/`. Pick `type:` by size — `task` for a discrete piece of work
(the default), `bug` for a defect, `feature` for user-facing scope, `epic` only for something
that will hold children.

## When a skill says "fetch the relevant ticket"

Read `issues/PROJ-n.md` in full, `## Log` included. The log carries the negotiation that led
to the note's current shape, and is usually where the real constraints are.

## Closing

Set `status: done` and append a `## Log` line saying why, in that order, in one edit. There is
no workflow to transition through and nothing validates the value, so a typo in `status:`
silently removes an issue from every query — copy the value, do not retype it.

## Pull requests

**PRs as a request surface: no.** If this repo has a GitHub remote, its PRs are code review,
not an intake queue. Nothing in triage reads them.

## Wayfinding operations

Used by `/wayfinder`. The **map** is one note; tickets are its children by `parent:`.

- **Map**: a note with `type: epic` and `labels: [wayfinder-map]`, holding the Notes /
  Decisions-so-far / Fog body.
- **Child ticket**: a note with `parent: [[PROJ-<map>]]` and a `wayfinder-<type>` label
  (`research` / `prototype` / `grilling` / `task`). Obsidian's backlinks pane on the map then
  lists them for free. Once claimed, set `assignee:`.
- **Blocking**: `blocked-by: [[PROJ-9]]` in the frontmatter.
- **Frontier query**: the map's children with `status: open`, an empty `assignee:`, and no
  entry in `blocked-by` whose own note is not `status: done`. In Dataview that is one table;
  from a shell, `grep -l 'parent: \[\[PROJ-<map>\]\]' issues/*.md` then filter. First in the
  map's body order wins.
- **Claim**: set `assignee:`. This is the session's first write.
- **Resolve**: append the answer to `## Log`, set `status: done`, then add a context pointer
  to the map's Decisions-so-far section.
