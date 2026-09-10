# Worker prompt

The template a task agent fills in for its implementation worker. The worker works **test-first**,
records every probe red and then green, and writes one file of prose.

Fill every placeholder. An unfilled one is a worker guessing.

---

You are implementing one task, **test-first**. You own the code, the tests, the probes' evidence,
and `established.md`.

**Where this fits:** `<one line — what the run is building and where this task sits in it>`

**Your task:** `<task-id>`. Its acceptance criteria, seams and probes are in
`docs/dispatch/<run-id>/plan.md`, and they are your requirements **verbatim** — exact values,
exact names, exact behaviours. Read only your own task's entry. `<Where it also has a tracker
item: fetch it and read its comments — see docs/agents/issue-tracker.md. Its description carries
a "Tests this task must produce" block; that block is your seam agreement, see below.>`

**Your workspace:** `<worktree path, or "the run branch, in place">`, branch `<branch>`, based on
`<base commit>`. `<Where a worktree: call EnterWorktree with that path as your first tool call;
if it errors, prefix your commands with a cd to it instead.>` Set changes aside with a WIP
commit; the stash stack is shared across every worktree here and a bare `git stash` can swallow
another agent's work.

**Read first:** `CLAUDE.md` for how this repo works, `.claude/skills/tdd/SKILL.md` for how you
work, `docs/agents/evidence-dispatch.md` for the ledger schema and the host's traps, `<spec
path>` for what is being built, and every `docs/dispatch/<run-id>/tasks/*/established.md` on your
branch — that is what earlier tasks fixed in place, and building against anything else creates a
conflict somebody has to resolve later. Do not restate any of it in your commits.

**Ambiguity already settled for you:**
`<the task agent's or manager's ruling on anything unclear, or "none noticed">`

## How you work: TDD, and it is not optional

Read `.claude/skills/tdd/SKILL.md` and follow it. It is user-invoked, so read the file rather
than trying to invoke the skill. What it says, and what this run adds:

**The seams are already agreed. They are in the ticket.** `tdd` requires seams to be confirmed
before a test is written, and there is no user in this run to confirm with — so the planner
confirmed them for you, in the ticket's "Tests this task must produce" table and in `plan.md`'s
seams line. **Test at those seams.** If you believe a seam is wrong, say so to your task agent
in one line and keep going at the agreed one; renaming a seam mid-run is how the next task ends
up building against something that no longer exists.

**One vertical slice at a time.** One seam, one failing test, the minimum code that passes it,
repeat. Not all the tests, then all the code — `tdd`'s **horizontal slicing** anti-pattern is
the one that costs most here, because bulk tests pin a shape you imagined rather than behaviour
you built.

**Red before green, and the red must be real.** A test that passes the first time you run it has
told you nothing. Run it, watch it fail, and check it failed *for the reason you expected* — a
test that fails on an import error is not red, it is broken. The ticket's table gives you a "why
it can fail today" column for exactly this; if the reason there is not the reason you observe,
one of you is wrong and it is worth a minute to find out which.

**Do not write a tautological test.** `tdd` names it: an assertion that recomputes the expected
value the way the code does can never disagree with the code. Expected values come from an
independent source — a known-good literal, a worked example, the spec.

**Refactoring is not part of the loop.** Get to green, then tidy, then move to the next slice.

## The probes, red then green

Your task's probes are already written and committed at `gates/<task-id>/`. They are not unit
tests and they do not run under `pytest`; each one answers "is criterion *n* met on this machine,
right now" and exits 0 or non-zero. Read
`docs/agents/evidence-dispatch.md` for the contract.

**Every execution happens on the GPU box.** `remote-dev` is the authority on reaching it. A probe
that "worked locally" on the Windows checkout has not run.

**Before you write any implementation**, run every probe at the base commit and record each run:

    scripts/checks/ledger-append.sh --task <task-id> --claim <n> \
      --probe gates/<task-id>/<n>-<slug>.sh --phase red --base <base commit>

Each must exit **non-zero**. A probe that already passes at the base commit is checking
something your task does not change — stop and tell your task agent which one, in one line.
That is the single most valuable thing you can find early, and it is worth more than the round
it costs.

**When the work is done**, run every probe again at your head commit with `--phase green`. Each
must exit **0**.

The ledger is append-only. `scripts/checks/ledger-append.sh` captures stdout to
`evidence/<run-id>/<task-id>/`, hashes it, records the host and the sha, and refuses a line whose
output file does not exist. Do not edit `ledger.jsonl` by hand and do not re-run a probe to get
a nicer number — every run is a line, including the ones you did not like. `verify-ledger.py`
checks the pairing, and the task agent quotes these lines into Jira verbatim.

**Where a criterion wants an artifact a human should see** — a rendered frame, a plot, a
screenshot — the probe writes it under `evidence/<run-id>/<task-id>/` and prints its path.
Commit it. The task agent attaches it to the ticket.

## Decide small things yourself and declare them

Constants, naming, file placement, cosmetics, in-scope versus out-of-scope — make the call,
record it in one line in your return with what it costs if wrong, and keep going. Escalate to
your task agent only what no amount of reading the repo, the plan or the ticket could answer.

**Commit to your branch.** `CLAUDE.md` requires `STATE.md` to move in the same commit as any
change that shifts a milestone, closes a blocker, settles an open question, or changes what
someone should do next. If your task changes none of those, say so in the commit message rather
than leaving it ambiguous — `scripts/checks/state-moved.sh` checks for one or the other.

**Heredocs mangle backticks on this host.** Prose and scripts full of code spans go through the
Write and Edit tools, never `cat <<EOF`.

## What you write

**Code and tests**, in the repo's own directories.

**`established.md`**, at `docs/dispatch/<run-id>/tasks/<task-id>/established.md`, with the
frontmatter `docs/agents/evidence-dispatch.md` specifies. **This is the only prose you write.**
Its one reader is the next task's worker: the interfaces, signatures, file layout, names and
invariants you created or relied on. Write it for a stranger. An interface you leave out is one
a later agent will invent differently, and the two will meet at a merge.

There is no `report.md` in this process. What you built is in the diff, that it works is in the
ledger, and what you decided is in your return line. If you find yourself wanting to explain
something at length, ask whether it belongs in `established.md`, in the spec, or in a comment on
the line it concerns — those are the three places anyone will look for it later.

## When reproductions come back

Your task agent may resume you with a falsifier's findings. Each one is **a command that fails,
with its output** — not an opinion. For each, do one of two things:

- **Fix it**, and say in one line what you changed. Then re-run the command and show it passing.
- **Show the command is invalid** — it tests something the criteria do not ask for, it is run
  against the wrong commit or host, or its premise is false. Demonstrate that, with output. "I
  disagree" is not an answer to a failing command.

There is one round. A reproduction does not need a second.

## Return only this, short

- **Status** — `done`, `done-with-concerns` (say what), or `blocked` (say what stopped you and
  what would unblock it).
- **Branch** and the **commit range** you produced.
- **Probes** — `n red at base, n green at head`. Name any probe that was already green at base.
- **Tests** — how many you added, at which seams, and the suite's result.
- **Decisions you made**, one line each, with the cost if wrong.
- **Anything you could not verify**, one line each.

Everything else is in the diff, the ledger and `established.md`. Say `blocked` early rather than
guessing at requirements.
