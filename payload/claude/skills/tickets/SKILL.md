---
name: tickets
description: Turn an approved scope into ownership units - tickets one owner each can take from start to merged, each with a reference to be judged against - lint them with plan-check.sh, and publish them as an epic and tickets in the configured tracker. Run as /tickets <spec path | epic key>.
argument-hint: "<spec path | epic key>"
disable-model-invocation: true
---

# Scope → tickets

Input: `$ARGUMENTS`. Read, in order:
1. `.claude/workflow/config.md` (its `## Protected paths` above all)
2. `.claude/workflow/ticket-template.md`
3. `.claude/workflow/definition-of-done.md`
4. the spec: its References, Protected paths and Domains

When `.claude/workflow/config.md` has a `## Project knowledge` section set to `Mode: on`, read
`.claude/workflow/project.md`'s Module map as well: it is what each ticket's `Owns` is
otherwise guessing at. In a multi-package repo (a `Packages:` line in that section), read the
Packages table there and the `<package>/PROJECT.md` module map of each package the spec
touches.

Every tracker read and write goes through the `tracker` agent, which owns the tracker's tools
and its adapter. You never call the tracker directly.

An epic key means: ask `tracker` to `read-epic` and `read-task` its children, read the linked
spec, and plan only what's missing.

Nothing is published before the operator approves the list.

## 1. Partition into ownership units

Each ticket must pass the four tests in `ticket-template.md`: ownable, checkable, finishable by
one owner, one owner start to merged. Plan the outcomes up front; the decomposition is for the
first waves only, and `/pad-run` writes later tickets once the first ones have landed.

- **Split by surface or module, never by concern.** A screen, an endpoint, a module, a
  migration. Never "all colours", "all fonts", "every button": a transverse sweep touches
  every file and every ticket collides with it.
- **Own files, disjointly.** Give each ticket the files it may write as `Owns`. Two tickets
  whose `Owns` overlap is a planning error: give the file to one, and let the other depend on
  it or request a change from its owner.
- **Shared files are `Touches`.** A registry, a router, an index every ticket adds one line to:
  list it under each ticket's `Touches`. Additions only; the `register-by-file` and
  `append-only-sorted` rules say how. A shared file that needs real rewriting belongs to one
  ticket.
- **Foundations land first.** A shared token set, a schema, a harness several tickets build on
  is one foundation ticket, and the others name it under `Depends on`. A cross-cutting concern
  that needs no code of its own is a line in the run's brief instead.
- **Name the reference.** Every build ticket points at what it is judged against, as the spec's
  References name it: a mock crop and viewport, spec outcome ids, a repro test, a baseline file.
  Link it; never paraphrase it. Where the spec marks an area `spike`, write a spike ticket that
  produces the reference and no product code, and make the area's build tickets depend on it.
- **Outcomes only where tests are the reference.** Then the ticket carries `## Outcomes`, each
  spec outcome in exactly one ticket. A surface outcome (`level: surface <name>`) lands in
  exactly one ticket too; one no ticket owns is a GAP that blocks the plan.
- **Mark protected tickets.** `Protected: yes` when the ticket's `Owns` or `Touches` matches a
  glob under the config's `## Protected paths` (storage, sync, auth, migrations, the data
  model). That ticket's tests come from a test-designer, and nothing else decides ceremony.
- **Depend only on use.** `Depends on` means this ticket builds on what the other produces: a
  name, a behaviour, data. Sharing a file is never a reason.
- **Tag resources.** Mark outcomes that need a serial resource from the config, by its tag. A
  device-only check is not a ticket: attach it to the ticket it verifies as a resource probe.
- **Size to one owner:** about 45 minutes of one agent's work. Larger splits by surface or
  module. There is no outcome or file cap: the ownership tests decide.

## 2. Lint, then show the list

Write the tickets to the plan file (section 3) as drafts, then run
`bash .claude/workflow/bin/plan-check.sh .work/plans/<slug>.md`. Fix every `OVERLAPS`,
`PROTECTED` and `DEPENDS` line before you show anything: each is a planning error, and the
script ends `PLAN FAIL` until they are gone. Read `HOTSPOTS` and `SWEEPS` as questions: a hot
`Touches` file shared by many tickets may want a foundation ticket; a sweep wants splitting.

Then present one table and stop for approval:

| Wave | Ticket | Reference | Owns | Touches | Protected | Depends on | Tags |
|---|---|---|---|---|---|---|---|

Below it: the script's `CRITICAL-PATH`, its `HOTSPOTS` and `SWEEPS` with what you did about
each, any spec outcome or area with no ticket (there should be none), the spikes, and any
decision you made that the spec didn't state.

## 3. Write the plan file

Write `.work/plans/<slug>.md`: the table, then every ticket's full body in the template, each
under `### <key or placeholder> — <title>`. The plan file is how a re-run avoids duplicating
tickets, and what `plan-check.sh` reads.

Write it with `Write`, not a heredoc — this is the longest prose file any skill here produces
and the one `.claude/workflow/writing-files.md` was written about.

## 4. Publish through the adapter

Send `tracker` one request per step, and record every key it returns in the plan file before
the next step. `tracker` refuses to duplicate an existing epic or ticket, so a re-run continues
where the last one stopped.

1. **Create the epic** (`create-epic`), or reuse the key you were given. Its description holds
   the intent, the non-goals, the references and the spec path: the working spec is not
   committed, so they have to live in the tracker too.
2. **Create each ticket** (`create-task` with the epic as `KEY`) in wave order, body from the
   template.
3. **Replace placeholders.** Now that keys exist, rewrite each `Depends on` section to name real
   keys, and send the corrected bodies back as `update` operations.
4. **Create every dependency edge** (`link`, with the ticket depended on as `BLOCKER`).
5. **Record the epic key** in the spec's header (`Tracker: <key>`), and copy the approved spec
   to `.work/runs/<epic key>/scope.md` in the main checkout (the parent of
   `git rev-parse --git-common-dir`). It is frozen from here: a change of scope is a new
   `/spec`.

If `tracker` reports `FAIL`, stop and report what exists, with the keys from the plan file.

## Mid-run: replan tickets

`/pad-run` writes new tickets during a run: a split after a ticket fails twice, the
next wave's decomposition, a finding from a wave review. Those go through sections 1 and 2 of
this skill, lint included, and the operator's approval at the next review gate, before they are
published as in section 4.

## 5. Hand off

Print the epic key, the wave table with keys, and: `/pad-run <epic key>`.
