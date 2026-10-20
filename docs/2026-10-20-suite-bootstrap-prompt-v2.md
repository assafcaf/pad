# Suite bootstrap: bring this repository's test suite into the tiered paradigm

Put this file at `.claude/workflow/suite-bootstrap.md` in every repo PAD is installed in, and run
it once, before the first epic that uses test tiers:

```
claude "Read .claude/workflow/suite-bootstrap.md and carry it out, start to finish."
```

One session, one agent, its own branch. Nothing else may run tests on this host while it runs.
Fill the operator inputs at the bottom first. Version 2, revised against the research report
`Test suite design standards` (2026-10-20); the standard each phase applies is named in brackets
so you can check the reasoning rather than trust it.

---

You are the **suite owner** of this repository. Nobody else owns `tests/`. Your mandate is one
sentence: *the repository stays safe to merge into, within a latency and memory budget*. This
run is your first and largest job: turn the suite that exists into the suite that mandate
needs. Every decision is written down with the measurement that justifies it, because the next
suite owner, and the operator, will read your reasons rather than trust them.

## The paradigm you are installing

A test is in one of three states, and the state decides where it lives and when it runs:

| State | Lives in | Written by | Runs | Decided by |
|---|---|---|---|---|
| **acceptance** | `tests/acceptance/<ticket>/` | the ticket's test-designer or owner | the ticket's own gate, the batch gate | the suite owner, after the wave: promote, rewrite, or retire |
| **CI** | `tests/` by module, tagged with a tier | the suite owner only | by tier, below | the suite owner |
| **dev** | the config's dev path | the owner | never committed | the owner |

CI tests are tiered by a **resource contract**, the way Google's test sizes and Bazel's
`size` attribute work [Google test sizes 2010; SWE at Google ch. 11; Bazel test encyclopedia].
A tier is what a test may touch and how long it may take, enforced by the runner, never an
opinion about "unit vs integration":

| Tier | Contract (enforced) | Per-test kill | Budget for the whole tier | Runs |
|---|---|---|---|---|
| `fast` | one process, no sockets, no subprocess, no sleep, no shared or global state, filesystem only under the test's temp dir; parallel-safe [Feathers 2005; Google "small"] | 60 s, target under 1 s [Bazel short; FIRST] | the operator's fast budget (2–5 min on one host) [Humble & Farley commit stage] | before every merge, on every candidate |
| `heavy` | one machine; localhost network, real stores, spawned processes, fresh interpreters; may build expensive module- or session-scoped fixtures [Google "medium"] | 300 s | about 6× the fast budget | once per landed batch, after landing |
| `epic` | anything: many processes, a GPU, a device, a shared resource; runs alone on the host [Google "large"; Bazel `exclusive`] | 900 s | none | on a fixed horizon: every k batches or nightly, and at the epic head [THEO every-3rd-day horizon] |

The tier is a marker (or the runner's equivalent) plus a row in `.claude/workflow/config.md`,
and a gate selects by tier. Nothing selects by file name and nothing selects by import graph.
Memory is a **declared budget per tier** that the harness uses to schedule runs; a run that
exceeds it is a scheduling failure, not a test failure [Bazel assumed RAM 20/100/300/800 MB;
no runner enforces RSS].

Until this run finishes the harness treats this repo as `Tiers: none` and gates as it does
today. When you finish, it gates by tier.

## Hard rules

1. **Measure before you move anything.** No test changes tier, file or shape without a number
   from phase 1 beside it.
2. **Unchanging tests.** A test you move keeps its assertions word for word; only a behaviour
   change may change a test [SWE at Google ch. 12]. A test you rewrite as a smaller one must
   kill every mutant the original killed (phase 7); say which.
3. **Every removal has a ledger line** in `.work/suite/REMOVALS.md`:
   `<file>::<test> | promote|rewrite|retire | <replacement or rule> | <evidence>`. A removal
   without a line is a bug in your work.
4. **Never prune by coverage.** Coverage-based minimisation loses more than half the fault
   detection in half the suites it was tried on [Yoo & Harman 2012]. The redundancy oracle is
   the mutation diff (phase 7); coverage is hygiene and may not drop per module.
5. **No skips, no xfails, no TODOs, no sleeps** added. A test you cannot place is a question
   in your report. A fixed `sleep` is never a fix: poll with a deadline [Luo et al. 2014: sleep
   fixes never fully removed flakiness].
6. **Production code changes only for test seams**: a session-scoped fixture hook, a way to
   pass a smaller worker count, a process-tree teardown. Each is listed in the report with its
   path. No behaviour change.
7. **One classifying rerun, never a loop.** A test that fails once is rerun **once**, in a fresh
   process, with shuffled order. Pass on rerun = `FLAKY`, recorded in `.work/suite/flakes.md`
   with both outputs, placed in `heavy`, and never counted as green [Gruber 2021; Bazel FLAKY
   status]. Fail twice = red, and you find out why.
8. **One commit per phase**, each with the phase name in the subject, so the operator can review
   phase by phase and revert one without the others.
9. **Everything the harness will read is a file** you leave behind (phase 8). Your chat report
   is a summary of those files, never the only copy of a decision.
10. **You do not touch the test-discovery surface except in phase 3**, and the phase-3 commit
    is the one the operator reviews line by line: runner config, every `conftest.py`, the
    runner plugin under `tests/_pad/`, CI files, `.claude/settings.json` [BenchJack 2026: an
    added `conftest.py` can mark every test passed].

## Phase 0. Set up and prove the host is quiet

- Create and switch to branch `suite/bootstrap` from the default branch. Work only there.
- Read `.claude/workflow/config.md` (Commands, Test paths, Dev tests, Protected paths, and
  `## Test regime` if present), `.claude/workflow/testing.md`, the runner's config in the repo
  (`pyproject.toml`, `pytest.ini`, `vitest.config.*`, …), `CLAUDE.md`, and every plugin the
  config's `## Plugins` table lists with `Extends: suite-owner`: a plugin adds steps and
  constraints to the phases below and names the repo's own resources (a GPU box, a simulator,
  a device) and canonical fixtures. Detect the runner from the Commands table; never assume
  pytest. If a step names a pytest mechanism, use your runner's equivalent, and if there is
  none, say so in the report and do the step by hand.
- Record the host: cores, total memory, free memory with nothing running. Compute the **memory
  budget** = free memory − the operator's reserve. Write all three to `.work/suite/host.md`.
- List every process already running that looks like a leftover test process (test workers,
  servers tests start, spawned interpreters). If any exist, stop and report them; do not
  measure on a dirty host.

## Phase 1. Measure the suite as it is

Run each test file **alone**, serially, sampling the process tree and memory every second, and
record per file: tests collected, wall seconds, peak processes, peak memory, exit code, failing
test ids, and per-test durations (`--durations=0` on pytest). Then run the whole suite once with
the repo's current parallel settings and record the same. Write `.work/suite/measure.jsonl`
(one line per run) and `.work/suite/durations.txt`.

Classify each file by what it does at runtime, from the measurement and a read of its fixtures:

- **sockets** (any network, including localhost): yes/no; which hosts;
- **spawns processes** (subprocess, multiprocessing, a server, a fresh interpreter): yes/no, how
  many at peak;
- **module- or session-scoped fixtures** that build something expensive: name and cost;
- **touches a shared resource** (a GPU, a device, a fixed port, a global store): which;
- **sleeps** or waits on wall-clock time: where.

Any test that passed above 85% of its would-be tier's per-test kill is flagged
`near-timeout` [Mozilla intermittents guidance]: it will flake under load.

Commit: `suite(bootstrap): phase 1 measurement`.

## Phase 2. Inventory what each test proves

For every test file, one row in `.work/suite/inventory.md`:

| File | Module it covers | Shape | What it pins | Candidate tier | Smells | Flags |
|---|---|---|---|---|---|---|

- **Module it covers**: the production module whose observable behaviour the assertions are
  about, through its public API [SWE at Google ch. 12: test via public APIs, behaviours not
  methods]. A file that covers several modules is split in phase 4.
- **Shape**: `module` (organised by behaviour), `ticket` (organised by the ticket or outcome
  that introduced it: sections headed by ticket keys, test names carrying outcome ids,
  docstrings that read as acceptance criteria), `repro` (a reproduction of one bug),
  `harness` (asserts on docs text, repo layout, lockfile contents, git history, decision files,
  config shape), `probe` (needs a resource this host lacks), `change-detector` (fails only on
  an intentional change: exact wording, a constant, private structure) [Google ToTT 2015].
- **What it pins**: the invariant in one line, in the repo's own words (`CONTEXT.md` if the
  knowledge layer is on). If you cannot say what breaks when the test fails, write `unclear`.
- **Candidate tier**: from the phase-1 contract only. Violates any `fast` prohibition →
  `heavy`; shared resource, many processes or `exclusive` → `epic`.
- **Smells**, from the catalogue with measured harm [Meszaros 2007; Bavota 2012; Spadini
  2018; PyNose 2021]: `eager-test` (several behaviours in one test), `mystery-guest`
  (depends on a file or fixture the reader cannot see), `general-fixture` (a fixture far
  bigger than the test needs), `assertion-roulette` (several asserts with no message),
  `conditional-logic` (branches or loops in the test), `no-assert` (asserts nothing),
  `magic-number` (an expected value computed by the code under test, or unexplained). Run the
  repo's test lint (Ruff `PT` rules or the stack's equivalent) and record its findings here.
- **Flags**: `duplicate-of <file::test>` when two tests pin the same invariant at the same
  boundary; `expensive-for-what-it-proves` when a `heavy` file's assertion would hold in
  process; `near-timeout` from phase 1.

Commit: `suite(bootstrap): phase 2 inventory`.

## Phase 3. Design the tiers and write the configuration (the reviewed commit)

- Install the runner's parallel, timeout, socket-blocking and random-order plugins if the repo
  lacks them (for pytest: `pytest-xdist`, `pytest-timeout`, `pytest-socket`,
  `pytest-randomly`), through the repo's own dependency tool, dev group.
- Runner config, the contract made real [pytest-socket; Bazel sandbox tags]:
  - markers `heavy` and `epic` registered, `--strict-markers`, unmarked = `fast`;
  - distribute **by file** (`--dist loadfile`);
  - sockets disabled by default; the `heavy` tier allows `127.0.0.1`/`localhost` only; `epic`
    allows what its tests declare;
  - a `fast` test that starts a subprocess fails at the call (the PAD runner plugin under
    `tests/_pad/` patches `subprocess.Popen` and `multiprocessing` for unmarked tests);
  - per-test timeout per tier: 60 / 300 / 900 s. These are kill limits tied to the tier
    class, never figures for "a host under load" [Bazel 60/300/900/3600]. The watchdog runs
    **outside** the test process, per shard, with process-group kill (`start_new_session` +
    SIGTERM, 10 s grace, SIGKILL) and, on Windows, a Job Object with `KILL_ON_JOB_CLOSE`
    (`taskkill /T /F` as the fallback). pytest-timeout's in-process `thread` method is not a
    watchdog: on Windows it hard-exits the runner with no teardown and no report;
  - a session-end check that fails the run when a process, port or temp dir started under the
    test tree is still alive [Bazel runner contract; nextest leak detection].
- Write `## Test tiers` in `.claude/workflow/config.md`:

```markdown
## Test tiers
Memory budget: <GB from phase 0>
| Tier  | Selector                      | Per-test kill | Budget | Declared GB | Runs                                        |
|-------|-------------------------------|---------------|--------|-------------|---------------------------------------------|
| fast  | `-m "not heavy and not epic"` | 60 s          | <s>    | <GB>        | owner before READY; every batch, before landing |
| heavy | `-m heavy`                    | 300 s         | <s>    | <GB>        | once per landed batch, after landing        |
| epic  | `-m epic`                     | 900 s         | none   | <GB>        | every <k> batches or nightly; at the epic head |
```

  Budgets and declared GB come from phase 1 (sum of the tier's files run serially, and the max
  peak), with the fast budget capped at the operator's figure. If the fast candidates alone
  exceed that figure, phase 4 must bring them under it; do not raise the figure.
- Add to the config's `## Protected paths` (or confirm the managed defaults are in force): the
  runner config, every `conftest.py`, `tests/_pad/`, CI files, `.claude/workflow/**`,
  `.claude/settings.json`. After this run, only a suite-owner ticket may change them.

Commit: `suite(bootstrap): phase 3 tiers, runner contract, protected surface`.

## Phase 4. Build the fast tier, by module

- Take a **coverage baseline** per production module on the untouched suite
  (`.work/suite/coverage-before.txt`) and a **mutation baseline**: one sampled mutant per
  covered line, arid lines (logging, string formatting, trivial getters) excluded, on the
  modules the fast candidates cover; record which mutants the old suite kills
  (`.work/suite/mutants-before.txt`) [Google mutation testing 2018/2021: diff-based, one
  mutant per line, no global score].
- Reorganise `fast` candidates by module: one file per module (or per public surface of a big
  module), named for the module. Split accretion files (sections headed by ticket keys) along
  module lines with `git mv` where a file maps to one module, so history follows. Demote the
  ticket key to a marker on the test (`@pytest.mark.ticket("KEY")`) so traceability survives
  the move without organising by it.
- Merge duplicates (`duplicate-of` rows): keep the one with the clearer boundary and name,
  ledger the other. Two tests are duplicates only when the mutation diff says so: the kept
  test kills every mutant the dropped one killed.
- Fix the smells the inventory found where the fix changes no assertion: split an eager test
  into one behaviour per test; replace a general fixture with a fresh minimal one; add the
  message an assertion-roulette assert lacks; move a mystery guest's data into the test. A fix
  that would change an assertion is a question in the report, not an edit.
- Every test in `fast` now passes the runner contract from phase 3 by construction: a test that
  needs a socket, a subprocess or a sleep is not fast. Mark it `heavy` and note why.
- Run the fast tier alone. Green, within budget. Record wall and peak.

Commit: `suite(bootstrap): phase 4 fast tier by module`.

## Phase 5. Consolidate the heavy and epic tiers

- Group whole-system tests by the thing they build: a sweep, a server, a store, a fresh
  interpreter. Where several files each build the same expensive thing, build it **once** at
  session scope and share it as an immutable shared fixture [Meszaros: Immutable Shared
  Fixture for expensive immutable state]; the measurement says how much that saves. A shared
  fixture that any test mutates stays per-module.
- A reproduction that spawns N processes to prove one invariant becomes two tests: the
  smallest N that still fails on the original bug (run the test against the parent of the
  fixing commit to find it) goes to `fast` or `heavy`; the original N goes to `epic`.
- Every `epic` test names, in its docstring, the **fidelity risk** it covers that no cheaper
  tier can (a real GPU, a real race at scale, a real device) and an **owner**; one that cannot
  is reduced to the cheapest tier that still kills its mutants [SWE at Google ch. 14: "a test
  rots" without an owner; a handful of large tests, never an enormous one].
- Mark every file `heavy` or `epic`. Run the heavy tier alone, distributed by file, with the
  configured workers, sockets limited to localhost. Green, within budget, zero leftover
  processes. Then the epic tier alone, exclusive. Record wall and peak for both.

Commit: `suite(bootstrap): phase 5 heavy and epic tiers`.

## Phase 6. Retire what the suite should not carry

- **Harness assertions** (`harness` shape) are architectural fitness functions, and they leave
  the behaviour suite [Ford, Parsons & Kua]: import and layering rules go to an import-linter
  contract (`.importlinter` or the stack's equivalent) run as a lint step; config-shape and
  layout checks go to `tests/architecture/`, which must run in milliseconds and is part of
  `fast`; assertions on README or doc prose are change detectors and are deleted or turned
  into a docs build check. For each, one line in `.work/suite/lints-needed.md`
  (`<what it checked> | <rule or contract> | <check in one line>`); PAD's `rules/` is where a
  submit-time lint will live. Ledger each as `retire | lint <rule name>`.
- **Change detectors** (`change-detector` shape): deleted, or rewritten to assert the behaviour
  that depends on the decision [Google ToTT 2015]. Ledgered.
- **Ticket-shaped duplicates** already merged in phase 4: ledgered there.
- **`unclear` tests**: do not retire. List them in the report for the operator.
- Nothing else is retired in this run. Retiring is the verdict the suite owner gives most
  rarely, and only with a replacement, a rule, or a mutation diff beside it.

Commit: `suite(bootstrap): phase 6 retirements`.

## Phase 7. Verify

- **Coverage per module after** (`.work/suite/coverage-after.txt`), diffed against the baseline:
  any module that lost lines → find the removal that caused it and revert it. Coverage is the
  hygiene floor, not the bar [Inozemtseva & Holmes 2014].
- **Mutation diff** (`.work/suite/mutants-after.txt`): every mutant the old suite killed is
  killed by the new suite. A surviving mutant that the old suite killed → the test that killed
  it was lost in a merge or rewrite; restore it. This is the bar [Google 2018; ACH 2025: 49%
  of useful tests are lost to a coverage-only filter].
- Run each tier alone on the quiet host: `fast` within its budget, `heavy` within its budget,
  `epic` green. Then run `fast` and `heavy` **at the same time** once: both must finish, total
  peak memory under the budget, zero leftover processes, no test above 85% of its kill limit.
  If they do not fit together, lower the heavy tier's declared workers until they do, and
  write the number in the config.
- **Order independence**: run the fast tier once more with the random-order plugin seeded
  differently. A failure here is an order dependency, the most common Python flake [Gruber
  2021: 59% of Python flakes]; fix it at the shared state, never by pinning order.
- The whole suite with the new config, once, as the merge gate will run it. Record the three
  numbers you will be judged on next epic: fast wall, heavy wall, peak GB.

Commit: `suite(bootstrap): phase 7 verification`.

## Phase 8. Leave the files the harness reads

- `tests/MAP.md`: module → test files → tier → the invariant each pins → owner. The brief
  writer reads this to tell every future owner which tests its ticket is expected to touch.
- `tests/acceptance/README.md`: what the quarantine is, the layout `tests/acceptance/<ticket>/`,
  the three-state bar a new acceptance test must meet (fails on the pre-change code for a
  precise reason, not an import error; passes after) [SWE-Cycle 2026], and that only the suite
  owner moves tests out. The directory is otherwise empty. Make sure the runner collects it.
- `tests/_pad/README.md`: what the runner plugin enforces per tier, in one table, so an agent
  knows what it will be judged by before it writes a test.
- `.work/suite/REMOVALS.md`, `flakes.md`, `lints-needed.md`, `inventory.md`, `measure.jsonl`,
  `host.md`, the two coverage files, the two mutant files: complete.
- `docs/decisions/NNNN-test-suite-bootstrap.md` (next number): the tiers and budgets chosen,
  the numbers before and after, the retirements and why, the seams added to production code,
  the flakes recorded, the open questions. Committed.
- `.claude/workflow/config.md`: `## Test tiers` filled; `Gate:` set to `tiers`; protected
  surface confirmed.

Commit: `suite(bootstrap): phase 8 map, quarantine, decision record`. Push the branch and open
a draft PR titled `Suite bootstrap: tiered test suite`. Do not merge it.

## Report

End with exactly this, nothing after it:

```
SUITE BOOTSTRAP <repo> — branch suite/bootstrap, PR <url>
Before: <files> files, <tests> tests, full run <wall> s, peak <GB> GB, <n> ticket-shaped files, <n> harness files
After:  fast <tests> tests <wall> s / budget <s> · heavy <tests> <wall> s / budget <s> · epic <tests> <wall> s
        peak fast+heavy together <GB> GB / budget <GB> GB · leftover processes 0 · near-timeout 0
Coverage per module: no module lost lines | <module>: reverted <removal>
Mutation diff: <killed before> killed before, <killed after> after, surviving-that-were-killed 0 | <list>
Order independence: pass | <test ids>
Moved: <n> · merged: <n> · rewritten: <n> · retired: <n> (all in REMOVALS.md)
Seams added to production code: <path: what> | none
Lints PAD must add: <n> (lints-needed.md)
Flakes recorded: <n> (flakes.md), each placed in heavy
Open for the operator: <unclear tests, assertion changes you did not make, tests that fit no tier>
```

## Operator inputs

Fill these before running:

- **Fast budget:** `<seconds>` — the longest a merge gate may take before landing. Start at
  `180` on a single host; the commit-stage rule is under five minutes, never above ten.
- **Memory reserve:** `<GB>` — what the host's desktop and other sessions keep; the test
  memory budget is free memory minus this. Measure it once with your normal apps open.
- **Epic horizon:** `<k batches | nightly>` — how often the epic tier runs between epic heads.
  Default: every 3 landed batches.
