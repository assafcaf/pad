# Writing outcome tests

Read before writing or changing a test. The principles are adapted from obra/superpowers
`skills/test-driven-development/writing-good-tests.md` (v6.3.0, MIT, © 2025 Jesse Vincent).

A test here exists to prove one outcome from the ticket, and to fail when that outcome breaks.

## Before writing the test body

1. **Name the outcome** it proves (`O1`, `O2`…) and put the outcome in the test name:
   `test_run_with_unknown_schema_is_refused_with_400`.
2. **Name the break.** Say which production change would make this test fail: a wrong
   branch, a missing side effect, a boundary case. If the only thing that fails it is an
   intentional decision (a constant, exact wording, private structure), it is a change
   detector. Test the behavior that depends on the decision instead.
3. **Pick the boundary.** Assert what a caller observes: the HTTP response, the file written,
   the exit code, the manifest record. Not private helpers, and not the framework's own
   mechanics.

## Rules

- **Expected values are literals or hand-checked fixtures.** Never compute them with the code
  under test or its helpers; a mirrored expectation passes whatever the code does.
- **Exercise the real thing.** Mock only what is slow, external or unavailable on this host:
  network, remote hardware, a simulator. Never assert on a mock itself. When mock setup
  outgrows the test, write an integration test with real components.
- **Doubles mirror reality.** A fake response has every field the real one has. Where call
  arguments or order are part of the contract, assert them.
- **Scripts are run, not read.** Test a script by running it on controlled input and
  asserting outputs, files and exit codes. Grepping its source proves nothing.
- **Test-only code lives in test utilities**, never as methods on production classes.
- **One outcome per test.** An "and" in the name means two tests.
- **Pass under load.** Several agents run suites on one host at once. Wait for async results
  (an awaited query, not a synchronous one that races the render), and size a slow test's
  timeout for that load. Fix a flake at its cause; a rerun only hides it. Give a test that waits a bounded
  timeout, so a hang fails the test instead of holding a suite slot, and leave no process
  or global state behind: the gate may run tests in any order, across workers.
  A test that starts a process stops its whole process tree, even when it fails: a child's
  children left running hold ports and suite slots for every later test.

## Permanent and development tests

- **Permanent tests** state the ticket's outcomes: behaviour other code and people rely on.
  The test-designer writes them in the red commit; red and green are proven on them, and they
  merge and stay.
- **Development tests** are scaffolding while the code goes green: an internal step, an
  intermediate shape, a helper. The owner writes them freely under the config's dev path
  (Commands `Dev tests`, default `tests/_dev/`) and never commits them.
- **At the end of the task** the owner triages each dev test: **promote** it (rewritten as an
  outcome test in a follow-up red commit; by the test-designer under the strict discipline) or
  **discard** it. The
  `dev-tests-stay-out` rule rejects a branch that commits a dev test, so none reaches the epic
  branch and no removal rule is ever needed for one.

## Three states

Every test is in one of three states, and the state says where it lives and who may change it.

| State | Where | Written by | Decided by |
|---|---|---|---|
| **acceptance** | anywhere the runner discovers tests; the ticket key in the file name, in the adapter's acceptance pattern (`runners/<runner>.sh acceptance-pattern <KEY>`: `prefill.KAN-12.test.ts`, `test_store_KAN_12.py`) | the ticket's test-designer or owner | the suite owner, after the wave: `VERDICT <KEY> <id> promote\|rewrite\|retire <tier> — §<n> <why>` |
| **CI** | by module, tagged with a tier (fast, heavy, epic) | the suite owner only | the suite owner |
| **dev** | the config's dev path | the owner | the owner; never committed |

An acceptance test is graded at submit: at the red commit it reports `failure` (not `error`)
with the text its `expects:` line states, and `pass` at the ticket head. Run tests only through
`bash .claude/workflow/bin/pad-test.sh` (`--role <role>`, `--ids`, `--failed`,
`--acceptance <KEY>`), never the runner itself; a whole file is not an id.

## Red, then green

1. Write the tests for the task's outcomes, and nothing else.
2. Run them. They must **fail on an assertion**, the configured red exit code
   (`config.md`'s Commands section — pytest's is `1`). A collection or import error is not red:
   add the minimal stub (a module, a function raising `NotImplementedError`) so the test runs
   and fails for the right reason.
3. Commit the tests alone: `test(<KEY>): <outcomes> [red]`.
4. Write the least code that makes them pass. Run them, the typecheck and lint; the merge gate runs the full suite.
5. Refactor with the tests green, then commit: `feat(<KEY>): <goal>`.

## Before reporting

Mutation check, in your head: for each realistic mutation (wrong constant, wrong branch,
missing side effect, empty return, missing validation of empty or malformed input), at least
one test fails. If none would, the outcome is unprotected. Add the test.
