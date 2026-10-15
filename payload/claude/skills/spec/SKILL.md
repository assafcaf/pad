---
name: spec
description: Turn an idea into the run's scope - intent, non-goals, references per area, protected paths and domains - by brainstorming together or by grilling the operator. Run as /spec [grill] <idea | ticket key | file>.
argument-hint: "[grill] <idea | ticket key | file>"
disable-model-invocation: true
---

# Idea → scope

Input: `$ARGUMENTS`. If it starts with `grill`, use grill mode; otherwise brainstorm mode. If
it names a ticket or file, read it first. Read `.claude/workflow/config.md` for paths.

The product of this skill is the run's **scope**: what the work is for, what it is not, and
for each area the **reference** that says when it is done (`.claude/workflow/definition-of-done.md`,
"The reference decides the ceremony"). The reference's class decides the ceremony downstream;
outcomes are written only where the reference is tests. Don't write code here.

**Reference, not paraphrase.** The spec links each reference (a mock crop, an outcome list, a
repro, a baseline file) and never restates it in its own words. A paraphrase is a hand-off
that loses intent; the owner reads the reference itself.

## 1. Size it, and say which size you picked

| Size | Signal | Artifact |
|---|---|---|
| **Small** | Changes a flow that already exists in this repo; one area with a reference | A short spec (one area), then `/tickets` |
| **Feature** | New behavior across a few areas, or an interface others use | A spec, then `/tickets` |
| **Spike first** | An area has no reference: no mock, no outcomes anyone can state, no repro, no baseline | Write the spec with that area's reference marked `spike`; `/tickets` makes a spike ticket that produces the reference, never product code |
| **Too big** | Several independent subsystems | Split into features first, agree the order, then spec the first one |

When unsure, take the larger size. If hidden complexity shows up later, step up and say so.

## 2. Understand before asking

Read the code, docs and recent commits the idea touches. Never ask the operator something the
repo can answer. If the repo has a glossary (`CONTEXT.md`, written by `/knowledge-layer` when
the config's `## Project knowledge` section is `Mode: on`), use its terms exactly, and say so
when an outcome needs a word the glossary does not have. In a multi-package repo, the
glossary of a package the idea touches (`<package>/CONTEXT.md`) adds that package's terms.

For each area, find what already exists to judge it by: a mock, an outcome list in an earlier
spec, a failing test or bug report, a baseline file. What exists is the reference; what doesn't
needs a spike.

## 3. Converge

Ask one question at a time. Use AskUserQuestion when the answer is a choice; lead with your
recommended option.

**Brainstorm mode** (collaborative):
- Clarify purpose, constraints and what success looks like.
- Propose 2–3 approaches with trade-offs, recommend one and say why. Cut features the goal
  doesn't need.
- Present the design in short sections (components and their interfaces, data flow, error
  cases, how each area is judged) and confirm each before the next.

**Grill mode** (adversarial):
- Map the idea as a tree of decisions and walk it depth-first. Resolve each decision before
  opening its children.
- For each decision, ask the hardest question it raises, and give the answer you would pick.
  Push back on vague words ("fast", "robust", "handle errors") until each is a number, a
  behavior, a reference or a non-goal.
- Probe the failure paths: what happens when the input is empty, huge or malformed, a
  dependency is down, the run is killed halfway.
- Stop when every leaf is decided or explicitly deferred.

## 4. Write the spec

Save to `.work/specs/<yyyy-mm-dd>-<slug>.md` with `Write`, not a heredoc
(`.claude/workflow/writing-files.md`):

```markdown
# <Title>
Status: draft | approved   ·   Tracker: <epic key, once it exists>

## Problem
Who needs what, and why now. Three sentences at most.

## Non-goals

## References
- <area>: what exists, linked — mock crop + viewport | outcome ids (below) | repro test |
  baseline file — or `spike: <what the spike must produce>` when nothing exists yet.

## Protected paths
- <glob> — paths whose diffs take the strict discipline (independently written red tests):
  storage, sync, auth, migrations, data model. Start from the config's protected paths.

## Domains
- <domain>: one line on what it covers. Bullets that orient the ticket split, not tasks.

## Outcomes
Only for areas whose reference is tests.
- [O1] Given …, when …, then …. (level: unit | integration | surface <name> | <resource tag>)

## Design
Components, the interfaces between them (exact names), data flow, error handling.

## Decisions
- <decision> — because <reason>. Rejected: <alternative> (<why>).

## Risks and unknowns
What could make a reference wrong, and how the plan finds out early.
```

`## Outcomes` is written only for areas whose reference is tests; drop the section when no area
has one. Where it is written, each user-visible **capability** names the surface it appears on
(a name from the config's `## Surfaces` section) and gets exactly one surface outcome: an
outcome at `level: surface <name>` that a person or an automated check can see on that surface.
One surface outcome per capability, no more, so one ticket can own it. A capability judged by
a mock instead has the mock crop as its reference.

Check it before showing it:
- no TBD or TODO
- no two sections contradict each other
- every area has a reference, linked not restated, or is marked `spike`
- every outcome is observable and names its level
- every capability has exactly one surface outcome naming its surface, or a mock crop on that surface; one with neither fails
- every protected-path glob matches something in the repo, or a path the spec creates
- every design element serves a reference

Then ask the operator to review the file. Iterate until they approve, then set
`Status: approved`. That approval is the **scope gate**.

## 5. Record what should outlive the spec

Working specs are not committed (`spec_commit: ask` in config).
- **Record durable decisions.** If the spec settled a decision a future reader of the code
  would need (an interface, a data format, a trade-off, a rejected approach), write
  `docs/decisions/NNNN-<slug>.md` in the format of `docs/decisions/README.md`. Show it and
  commit it once approved.
- **Ask once about promotion:** "Promote the full spec to `docs/specs/`?" Default no.

## 6. Hand off

Run `/tickets <spec path>` in the same session, so the scope gate and the ticket-list gate are
one conversation.

The approved spec is the run's `scope.md`. Once `/tickets` has created the epic, set the spec's
`Tracker:` line and copy it to `.work/runs/<epic>/scope.md` in the main checkout (resolved like
`run-log.sh`, so it is the same file from any worktree). The scope was frozen at the scope
gate; the copy changes nothing else in it, and nobody edits it during the run. A change of
scope is a new `/spec`, not an edit; rulings made during the run go to the brief's
`## Rulings`.
