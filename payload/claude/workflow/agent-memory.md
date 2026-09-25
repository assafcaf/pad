# Agent memory

The agents `/batch-implement` runs have a persistent memory: `memory: project` in their
frontmatter. Each one has `.claude/agent-memory/<agent name>/MEMORY.md`, which Claude Code loads
into the agent's context every time it starts (the first 200 lines). It lives in the main
checkout even when the agent works in a worktree, and it is committed, so every run and every
machine inherits it.

Its purpose is narrow: **an agent that hit a wall once should not hit it again.** A command that
is denied here, a tool that can't do what it looks like it can, a gate that fails for a
non-obvious reason — and the way that works instead.

## When to write a line

Only after something **failed or blocked you**, **you found what works**, and **the next run of
you would hit it again**. All three.

Not:
- a fact about one task (a prop name, a ticket's quirk) — it's wrong for the next task;
- anything your agent file, `config.md`, `CLAUDE.md` or `project.md` already says;
- a guess, a preference, or something that went fine;
- a fact about the product's code (an invariant, a domain rule): that belongs in
  `project.md`, which the operator writes. Put it in your report's `NOTES` instead;
- a finding (below).

## A memory line or a finding

Memory is for recipes: how you get past a wall on your own. Some walls aren't yours to get
past, and a line that works around them hides them. It's a **finding**, not a memory line,
when:
- the fix would make you act against your agent file: the file is what's wrong;
- it cost another agent, not you — someone waited on you, or your report went astray;
- it's the harness, a tool or another agent misbehaving, not something you did.

One agent sees one wall. The same defect reached several agents in one run (a worktree moved
out from under a code-writer, a tracker, an owner and the merger), and each wrote its own
workaround. None of them connected it. A merger's line — *hold everything on a bad sha* —
followed its agent file and stalled every other task for an hour.

Write a finding as one line appended to `.work/runs/<run id>/incidents.md`, with
`printf '%s\n' '<line>' >> <path>` (the run log's folder, so other agents can append at the
same time):

```
<UTC time> <your agent> <KEY> — <what happened> — <what it cost: minutes, a retry, a lost report> — <what unblocked it>
```

Write one whenever you waited on, or were blocked by, something outside your own work, even
when you found your way past it. It takes no judgement: the run's review
(`/batch-implement`, "Review the run") and the curator decide what it means. You may still add
a memory line for your part of the workaround, if the rules above allow it.

## How to write it

One line, under about 200 characters, in this shape:

```
- <do this / don't do that, with what works instead> — <why, one clause> (<task key>, <yyyy-mm-dd>)
```

For example:

```
- Branch with `git worktree add`, not `git checkout -b`: checkout is denied in settings.json (E5-T3, 2026-09-23)
```

1. Read `MEMORY.md` first. If a line already covers it, correct that line instead of adding one.
2. Change the file with `Edit` only, never `Write`. Agents of the same kind run in parallel and
   share this file. If someone changed it since you read it, `Edit` fails and you re-read;
   `Write` would silently drop their line.
3. At most two lines per task. Keep everything in `MEMORY.md`, with no extra files, so the
   whole memory loads and the curator sees all of it.

## Who keeps it clean

Each agent owns its own memory. At the end of every epic, `/batch-implement` reviews the run and
then runs the `memory-curator`. The curator keeps, tightens, merges or deletes lines against the
rules above, and never invents a lesson. It works across agents: it groups lines and incidents
with one cause, copies a lesson to every agent that hits the same wall, and removes a line
whose cost falls on others. What memory can't fix — the agent files, the harness — it writes up
as a proposed change. It commits the result on the epic branch, so its changes show in the
epic's PR.
