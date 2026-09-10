# Silent-failure audit prompt

The template the manager fills in **once**, at the finish, and only when some task in the run ran
on the `judgment` track. One agent, one question, one pass, no rounds.

This is the only reading review in this process, and it exists because of one measured case.

> On `PROJ-17`, `service/runs.py` built the publisher's `task_dir` from the **task** name where
> upstream writes into the **environment** name. At that pin the two coincide, so every test
> passed and every probe would have gone green. A task registering a differently-named
> environment would have published nothing, raised nothing, and reported a dataset URI for an
> empty dataset. It was found by reading, and it produced the best code fix of the run —
> `8ee9b72`, a guard plus 110 lines of test.
>
> No probe catches that. It is not a bug today; it is a bug the day something else changes.

---

You are reading one run's whole diff to answer **one question**:

> **Where can this code do the wrong thing without saying anything?**

Not "is this correct" — the probes and the falsifier answered that, and they answered it by
running the code. Yours is the failure that leaves no trace: the empty result reported as a
success, the silent skip, the default that is right today, the exception swallowed, the loop
that publishes nothing and returns cleanly.

**Your scope:** `<merge-base>..<head>` on branch `<branch>`.

**Your workspace:** `<path>`. Call `EnterWorktree` with that path as your first tool call; if it
errors, prefix your commands with a `cd` to it instead.

**Read first:** `CLAUDE.md`; `docs/dispatch/<run-id>/plan.md` for what each task was for; and
every `docs/dispatch/<run-id>/tasks/*/established.md` — the invariants each task fixed in place
are where a coincidence hides.

**Get the diff yourself:**

    git diff -U15 <merge-base>..<head>

Read `-U15`, not `--stat`. The context is where the assumption lives.

## What you are looking for

Six shapes. They are the ones that have actually cost this repo, and each has a question that
finds it.

**Correct by coincidence.** Two names, two paths or two counts that agree today because of a
convention nobody wrote down. *Ask: what would have to change elsewhere for these to diverge, and
would anything notice?*

**The empty success.** A loop that finds nothing, publishes nothing, and returns a result that
looks like a result. *Ask: what does this return when its input is empty, and is that
distinguishable from working?*

**The swallowed signal.** A broad `except`, a `|| true`, a `continue` on error, a default that
fires on a missing key. *Ask: what does the operator see when this path is taken?*

**The unpinned assumption.** A behaviour depending on an upstream version, a registration order,
a filesystem layout, a container's default. *Ask: is this recorded in the spec's unverified
list, and does the code fail loudly if it changes?*

**The guard that guards the wrong thing.** A validation that runs on the value after it was
already used, or on one field of two that must agree. *Ask: between the check and the use, can
the thing being checked change?*

**The record that lies.** A manifest, a count, a status or a URI written before the work it
describes is durable, or written from what was intended rather than what happened. *Ask: is
this field derived from an observation, or from a plan?*

## The rule

**Every finding names a line and states the change elsewhere that would make it fire.** A
concern that cannot name what would trigger it is not yet a finding — it is a thing to read
harder.

You may not have a reproduction. That is expected and it is the whole reason you exist: this
class does not reproduce today. But you must be able to say *"when X changes, this does Y and
nothing says so"*, with X concrete.

**Where the answer is "record it, do not build it"**, say that. `CLAUDE.md` is explicit that
speculative scope is not welcome here, and the spec's §11 is the register for unverified
upstream behaviour. Three lines in the spec and a docstring is a complete fix for a coincidence
that is not yet a defect. Do not propose multi-environment support for a run that uses one.

## What you are not

- Not a standards review. `run-checks.sh` and the falsifier cover what is mechanical.
- Not a spec review. The probes answered whether the criteria are met.
- Not a second opinion on anything already tested. If a probe covers it, it is covered.
- Not a style pass. Naming, placement and cosmetics were the task agents' calls and they are
  made.

If you find yourself writing about anything but a silent failure, stop and cut it. On `PROJ-17`
the reviewing agents wrote 134KB of `review.md` and the withdrawal rate was 84%; the single
finding of this shape was worth more than all of it.

## What you return

No file. A list, most severe first, each of four parts:

1. **The line** — `file:line`, opened and confirmed, not an offset into a diff.
2. **The coincidence or the swallow** — one sentence on what is true today that makes this safe.
3. **The trigger** — the concrete change elsewhere that makes it fire.
4. **The consequence, and its silence** — what goes wrong, and what the operator sees while it
   does. If the answer to the second half is not "nothing", it is not this pass's finding.

Then one closing line: `n findings` or `clean`, plus the shapes above you checked and found
nothing in, one line each.

Say `clean` plainly when it is. A pass that manufactures a concern costs a fixer round and
teaches the next run to discount this one.
