# Definition of done

Done is a ticket's reference met, shown by evidence kept at merge, and judged by someone other
than the writer. The independent judge's opinion enters into it; the writer's never. Every
check the merge gate lists below is run by a script; commands come from `config.md`.

## The reference decides the ceremony

Every ticket names its acceptance reference (`## Reference`). The reference's class decides who
writes it, how red is proven, what evidence is kept and who judges. A diff that touches a
protected path (the ticket's `## Protected` says `yes`, derived from its Owns and Touches against the
config's protected paths) takes the strict class whatever else it is. A piece of work with no
reference yet is a **spike**: its ticket produces the reference and never product code.

| Class | Who writes the reference | Red proof | Evidence at merge | Judge |
|---|---|---|---|---|
| **Visual** — the surface has a Render command in the config's `## Surfaces` | The operator or designer: a mock crop and viewport, linked from the scope | A render of the base commit beside the mock, showing the gap | The render pair (mock, render at the merged commit) under `.work/runs/<epic>/evidence/<KEY>/` | A fresh-context evaluator agent comparing the pair; a pixel diff only in a pinned environment |
| **Contract tests** (strict) — the diff touches a protected path | A test-designer, as a blocking child of the owner, in a `[red]` commit; the tests are read-only to the owner | `verify-red.sh` at the red commit | Outcome → test ids, the red commit, the green run | `weakened-tests.sh` and a reviewer; `merge-task.sh` rejects a protected diff with no red commit (`needs-strict`) |
| **Behaviour tests** (standard) — spec outcome ids, no protected path | The owner writes the tests first, in their own red commit | `verify-red.sh` at the red commit | Outcome → test ids, the green run | `weakened-tests.sh` and a fresh-context evaluator checking the tests say the outcomes |
| **Reproduction** — a bug | The owner (or the reporter) writes the repro first | The repro fails at the base commit | The repro failing at base and passing at the merged commit | An evaluator confirming the repro shows the reported symptom |
| **Golden / metric** — a baseline file | A spike or the operator records the baseline and the target | The metric table at the base commit misses the target | The metric table against the baseline | An evaluator against the scope's thresholds |
| **Human** — nothing mechanical can say it | The operator, in the scope: what to look at | None; say so in the ticket | What to look at, listed in the wave's review packet | The operator, at the wave review |

## An outcome

When the reference is tests, it is a list of outcomes. An outcome is one observable result at a
boundary someone outside the code cares about: a response, a file on disk, an exit code, a
record in the manifest, an error the caller sees.

- Written as "Given <state>, when <action>, then <observable result>".
- Names its test level: `unit`, `integration` (real components, host-runnable), `surface
  <name>`, or a serial resource tag from `config.md`.
- Testable by one or more tests whose names say the outcome.

"Refactor X", "add a helper" and "improve logging" are not outcomes. They are means, and
belong inside a ticket whose outcome needs them.

## The merge gate

Every class passes the same gate, run on the tree that lands, alone or as part of a batch. Nothing switches a
check off.

- **Affected tests** pass, and the outcome tests among them.
- **Lint**, **typecheck** and **build** are clean.
- **`weakened-tests.sh`** finds nothing: no commit after the red commit changed a test file;
  the diff adds no `skip`, `xfail` or disabled test, deletes no existing test that a
  test-removal rule doesn't explain (`.claude/workflow/rules/`), and leaves no `TODO` in code
  it adds. The tests it adds keep the test-authoring rules (`task-submit.sh`).
- **Protected-path guard**: a protected diff without an independently authored red commit is
  rejected.
- **Evidence capture**: the class's evidence is written under the run's evidence directory.
- **Ledger and run-log** are written by the script, not by an agent: status moves to done,
  naming the merge commit, the red commit (if any), the commands run and their results.

## A ticket is done when

1. **The reference is met**, judged by its class's judge, with its evidence kept.
2. **Red was proven**, where the class has a red proof. For tests, `verify-red.sh` shows them
   failing at the red commit with the configured red exit code: the tests ran and failed, as
   opposed to never ran (a file that fails to import is not red). Outcomes on a serial
   resource are proven green there instead (item 4), since they can't run on the host.
3. **The merge gate passed** on the epic branch.
4. **Serial-resource outcomes passed** where their resource lives, run by the orchestrator at
   the merged commit, with the output kept in the run log.
5. **It stayed inside its ticket.** Its writes are within the ticket's Owns and Touches
   (Touches append-only); `task-submit.sh` rejects anything else.

## An epic is done when

1. Every ticket is done, and the operator has reviewed every wave.
2. The full suite and lint pass at the epic branch head.
3. The development record (`docs/decisions/`) has an Outcome section for this epic: what was
   built, what changed from the scope, and why.
4. The epic branch is pushed and a draft PR is open, linking the epic.
5. The epic is in the review status, and the run's rulings are listed in the PR body.
