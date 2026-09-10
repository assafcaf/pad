# Deep planner prompt

The template the manager fills in once, at setup. This planner reads widely so nobody downstream
has to, and it does one thing `/dispatch`'s planner does not: **it turns every acceptance
criterion into an executable probe, and writes the conceptual test list into the ticket.**

Fill every placeholder. An unfilled one is a planner guessing.

---

You are planning one run of work. Everything you learn that another agent will need goes into
`plan.md`, the probes, and the tickets. Nobody downstream reads the spec or the task bodies
again.

**The work:** `<the tracker key(s), or the user's description, verbatim>`

**Your workspace:** `<path>`. Call `EnterWorktree` with that path as your first tool call; if it
errors, prefix your commands with a `cd` to it instead. You write `plan.md` and the probes there
and **commit them** — they must be on the run branch before the first worker starts, or the
workers inherit a branch without their own probes.

**Read, in this order:**

1. `CLAUDE.md` — how this repo works.
2. `docs/agents/evidence-dispatch.md` — the tracks, the knobs, the ledger schema, the probe
   contract, the Jira block formats. You write the file the whole run reads; match it exactly.
3. `.claude/skills/tdd/SKILL.md` — what a good test is, and what a seam is. You are naming the
   seams the workers will test at, so you need its vocabulary, not a summary of it.
4. `<spec path, or "no spec — the work is described above">`.
5. Every task in the run. Where they come from a tracker, follow `docs/agents/issue-tracker.md`
   and read each task's **comments** as well as its body — the comments carry the constraints
   that shaped it.

## What `plan.md` must carry

**Identity.** The run id and every task id, at the top. Where the work came from a tracker,
these are its keys; otherwise derive short kebab-case slugs, and this file is then the only place
any agent resolves an id from.

**The graph.** Every task and every blocking edge, as a diagram plus a line per edge saying why
the edge exists. A dependency nobody can see the reason for is one somebody will merge away.

**Per task, six things:**

- **Intent** — one line: what this task is for, and where it sits in the run.
- **Acceptance criteria** — numbered, exact, checkable. Where the task has a tracker item these
  are its criteria **verbatim**; say so if the tracker's are incomplete. Where there is no
  tracker, you are writing them and they are the only requirements that will ever exist.
- **Probes** — one per criterion. The path, and one line on what the probe actually does. A
  criterion with no probe is a finding you report in your return line; see **Criteria that
  cannot be probed**.
- **Complexity** — `low` · `medium` · `high`, one sentence. The manager picks the model from
  this line and reads nothing else to do it. Grade the *work*: `low` means implementation is
  transcription plus testing.
- **Track** — `execution` · `mechanical` · `judgment`, one sentence of rationale, per the table
  in `docs/agents/evidence-dispatch.md`. Be honest and be specific: **`judgment` is for code
  that can be silently wrong** — anything that selects, publishes, resolves a path, retries, or
  decides what to skip. A task that only builds an image or wires a compose file is
  `mechanical`. A task that ships no code at all is `execution`.
- **Seams and tests** — the interfaces this task will create that later tasks build on, and, per
  seam, the behaviours a test must pin. This is the source of the ticket block below, and the
  worker's TDD depends on it: `.claude/skills/tdd/SKILL.md` requires seams to be agreed before a
  test is written, and in an autonomous run **you are the agreement**.

**The collision matrix** — only if the frontier will ever be wider than one task. One row per
pair that could share a wave: the two tasks, the files and interfaces each touches, whether they
overlap. Record this repo's standing overlap once — `CLAUDE.md` requires every task to update
`STATE.md`, so every pair collides there.

**If the graph is a chain**, say so in one line at the top and write no matrix. On `PROJ-17` the
frontier was one task wide in all five waves and the matrix went unused.

## Writing the probes

One probe per criterion, at `gates/<task-id>/<n>-<slug>.sh`, committed, mode `755`.

The contract, in full: **no arguments, prints what it checked, exits 0 for met and non-zero for
not met.** It may build an image, curl a port, count files, or shell into the running stack. It
is not a unit test and does not run under `pytest`.

Rules that make a probe worth having:

- **It must be able to fail.** Before you commit it, ask what change would make it exit
  non-zero. If the answer is "none", it is decoration — the run will catch you anyway, because
  the worker has to record a red run at the base commit, but you will have wasted the round.
- **It asserts the criterion, not the implementation.** "The policy answers `/healthz` with the
  model id" is a criterion. "Line 40 of `Dockerfile.policy` says `CMD`" is not.
- **It says what it checked** on stdout, in whatever detail a human would want when it fails.
  That output is captured into the ledger and quoted in Jira, so it is the evidence.
- **It is written with the Write tool, not a heredoc.** Backticks in a heredoc are re-evaluated
  on this host and silently strip what is between them — `docs/agents/evidence-dispatch.md` has
  the trap.
- **It runs on the box.** Every execution in this repo does. Write it assuming it is running
  there; `remote-dev` is the authority on getting there.

Where a criterion needs an artifact a human should see — a rendered frame, a plot, a screenshot
— have the probe write it to `evidence/<run-id>/<task-id>/` and print the path. The task agent
attaches it to the ticket.

## Criteria that cannot be probed

Some cannot, honestly. "The abstraction is the right one" is not executable. When you hit one:

1. Say so in `plan.md` under the criterion, in one line, with why.
2. Put the task on the `judgment` track — that is what the track's reading pass is for.
3. Name it in your return line. The manager rules on whether it stays as a reading criterion or
   leaves the run.

**Do not write a probe that pretends.** A probe that greps for a string as a proxy for a design
property is worse than an admitted gap: it goes green, and it goes green forever.

## Writing the test list into the ticket

For each task **that has a tracker item**, after `plan.md` is committed, append one block to the
ticket description with `editJiraIssue`, exactly as `docs/agents/evidence-dispatch.md` specifies
— between the `evidence-dispatch:tests` markers.

**Append-only, under the markers.** Read the description first. Never rewrite a human's text;
never move their content; if a block from a previous plan is already there, replace only what
lies between the markers.

The block carries two tables:

- **Tests this task must produce** — conceptual, one row per behaviour: the seam, the behaviour
  under test, and **why it can fail today**. That last column is what makes the worker's red
  step real. "It should work" is not a reason a test can fail; "nothing raises, and the run
  reports a URI for an empty dataset" is.
- **Probes this task must pass** — criterion number, probe path, and what green means.

Write both for a stranger. The worker reads the ticket, not your reasoning.

A task with no tracker item skips this silently, and its `plan.md` entry is the whole
requirement.

## Return, short

- The run id, the task count, and whether the graph is a chain.
- Each task: id, track, complexity, probe count — one line each.
- **Any criterion you could not make executable**, with the task and one line on why.
- Any task whose criteria were too thin to plan from.
- Which tickets you wrote a test block into, and any you could not.
- The path to `plan.md`.

Everything else is in the file.
