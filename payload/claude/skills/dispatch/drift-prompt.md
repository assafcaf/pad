# Drift planner prompt

The template the manager fills in before every wave from the second on. One question, one cheap
agent. The deep planner that produced `plan.md` is [`planner-prompt.md`](planner-prompt.md).

---

You are checking one thing before a wave is dispatched: **is this run still inside its plan?**

**Your workspace:** the run branch's worktree, `<path>`. Call `EnterWorktree` with that path as
your first tool call; if it errors, prefix your commands with a `cd` to it instead. The manager
stays out of this worktree, so it is free while you work.

**Read:**

- `docs/dispatch/<run-id>/plan.md` — what we said we would build. It is frozen; you never edit it.
- `docs/dispatch/<run-id>/tasks/*/established.md` — what the completed tasks actually created.
- `docs/dispatch/<run-id>/tasks/*/verdict.md` — how each one ended.
- `docs/dispatch/<run-id>/rulings/` — what the manager decided along the way.
- `git log` on the run branch.

Those files and that log are the whole input. Diffs, task bodies and the spec are somebody
else's job: the question is whether reality and the plan still agree, not whether the code is
good.

**Answer, comparing the two:**

- Has a completed task established something the plan did not anticipate — a different
  interface, an extra file, a name later tasks were told to expect differently?
- Has a ruling changed what a not-yet-dispatched task should do?
- Does the collision matrix still hold for the tasks about to be dispatched, given what has
  actually landed?
- Is a planned dependency now wrong — satisfied early, or newly required?

**Write `docs/dispatch/<run-id>/drift/wave-<n>.md`** with the frontmatter
`docs/agents/dispatch.md` specifies (`kind: drift`, `status: on-plan` or `off-plan`), and commit
it to the run branch.

**Return, short:** `on-plan` or `off-plan`; if `off-plan`, one line per divergence naming the
task and what changed, and one line on what it means for the wave about to go out.

Say `on-plan` plainly when it is. A drift check that manufactures concerns costs a ruling for
nothing.
