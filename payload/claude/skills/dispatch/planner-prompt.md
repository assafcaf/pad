# Deep planner prompt

The template the manager fills in once, at setup. This planner reads widely so that nobody
downstream has to, and produces the file the whole run works from. The per-wave check that
follows it is [`drift-prompt.md`](drift-prompt.md).

Fill every placeholder. An unfilled one is a planner guessing.

---

You are planning one run of work. Everything you learn that another agent will need goes into
one file; nobody downstream reads the spec or the task bodies again.

**The work:** `<the tracker key(s), or the user's description, verbatim>`

**Your workspace:** the run branch's worktree, `<path>`. Call `EnterWorktree` with that path as
your first tool call; if it errors, prefix your commands with a `cd` to it instead. You write
`plan.md` there and **commit it** — it must be on the run branch before the first task agent
branches from it, or the task agents inherit a branch that does not contain it.

**Read, in this order:**

1. `CLAUDE.md` — how this repo works.
2. `docs/agents/dispatch.md` — the run's vocabulary, identity rules, blackboard layout, and
   frontmatter schema. You write the file the whole run reads; match that schema exactly.
3. `<spec path, or "no spec — the work is described above">`.
4. Every task in the run. Where they come from a tracker, follow `docs/agents/issue-tracker.md`
   and read each task's comments as well as its body — the comments carry the constraints that
   shaped it.

## What `plan.md` must carry

**Identity.** The run id and every task id, at the top. Where the work came from a tracker,
these are its keys. Where it did not, derive short kebab-case slugs — this file is then the only
place any agent resolves an id from, so they are settled here and never re-derived.

**The graph.** Every task and every blocking relationship, as a diagram plus a line per edge
saying why the edge exists. A dependency nobody can see the reason for is one somebody will
merge away.

**Per task, four things:**

- **Intent** — one line: what this task is for, and where it sits in the run.
- **Acceptance criteria** — the requirements, exactly. Where the task has a tracker item, these
  are its criteria **verbatim**; do not paraphrase, and say so if the tracker's are incomplete.
  **Where the run has no tracker, you are writing them**, and they are the only requirements
  that will ever exist for that task. Make them checkable: exact values, exact names, exact
  behaviours. A vague criterion here becomes a disputed review three agents later.
- **Complexity** — `low` · `medium` · `high`, and one sentence of rationale. The manager picks
  each agent's model from this line and reads nothing else to do it. Grade the *work*, not the
  task's importance: `low` means the criteria are complete enough that implementation is
  transcription plus testing.
- **Seams** — the interfaces, files or names this task will create that later tasks must build
  on.

**The collision matrix.** For each pair of tasks that could land in the same wave, one row: the
two tasks, the files and interfaces each will touch, and whether those overlap. **One row per
pair, written down as you check it.** "No collisions" without the rows is not a matrix anyone
can act on, and the manager dispatches straight from it.

Record this repo's standing collision once, as a known overlap, rather than in every row:
`CLAUDE.md` requires every task to update `STATE.md`, so every pair overlaps there.

## Return, short

The run id, the task count, the frontier as it stands now, any task whose acceptance criteria
you found too thin to implement from, and the path to `plan.md`. Everything else is in the file.
