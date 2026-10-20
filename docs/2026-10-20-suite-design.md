# Suite design: the suite owner's standard

Read on every start, before the brief and the wave's packet. This is what you know; the
bootstrap prompt is this standard applied once to a suite that predates it. Every rule carries
its source in brackets so you can judge it rather than obey it; the sources are in
`docs/research/test-suite-design-standards.md`. A repo adds to this standard through rules
and plugins (`config.md`, `rules/`, `.claude/pad-plugins/`); nobody edits it in place, since
`/pad-update` replaces it.

## 1. Mandate and what you measure

*The repository stays safe to merge into, within a latency and memory budget.* Two halves,
both yours: the tests, and the infrastructure they run on.

You are judged on trends, not a score [Google computes no global mutation score; 2021]:

| Metric | Direction | Where it comes from |
|---|---|---|
| Fast-tier wall on the merge path | at or under budget, flat as the suite grows | `gates.jsonl` |
| Surviving mutants on changed lines | down | the mutation diff per wave |
| Tests in quarantine, and their age | down; none past the cap | `flakes.md` |
| Setup work per test body (commands, heavy imports, process starts) | down | phase-1 style measurement per wave |
| Tests whose invariant is `unclear` | zero | `tests/MAP.md` |
| Gate runs over budget | zero twice in a row | `gates.jsonl` |

## 2. Tiers are resource contracts

A tier is what a test may touch and how long it may take, enforced by the runner plugin, never
a label [Google test sizes 2010; SWE at Google ch. 11; Bazel `size`]. Cost follows from the
contract; a test that needs more than its tier allows is in the wrong tier, not a special case.

| Tier | May touch | Per-test kill | Flake rate to expect | Runs |
|---|---|---|---|---|
| `fast` | one process; no sockets; no subprocess; no sleep; no shared or global state; files only under its temp dir; parallel- and order-safe [Feathers 2005] | 60 s, target < 1 s [Bazel short; FIRST] | ~0.5 % at Google's scale | every candidate, before landing |
| `heavy` | one machine; localhost; real stores; spawned processes; fresh interpreters; expensive immutable session fixtures | 300 s | ~1.6 % | once per landed batch, after landing |
| `epic` | anything, exclusive on the host; a GPU, a device, many processes | 900 s | ~14 % [Google 2017: flakiness tracks binary size r² 0.82, RAM 0.76] | on the horizon (every k batches or nightly) and at the epic head |

Target mix: most tests fast, a thin heavy layer, a handful of epic tests each naming the
fidelity risk only it covers and an owner [SWE at Google ch. 14: "a test rots" without one;
80/15/5 as of 2020]. Memory per tier is a declared scheduling weight the harness uses to admit
runs [Bazel 20/100/300/800 MB]; exceeding it is a scheduling event, not a test failure.

## 3. What a good test is

Each rule is a check you run in your head over every test you promote, rewrite or review.

1. **Test behaviours, through public APIs.** One observable behaviour per test, named for it;
   the name reads as a sentence about the module, never about a ticket. [SWE at Google ch. 12]
2. **State, not interactions.** Assert what the caller observes (a response, a file, an exit
   code, a record). Asserting that a mock was called in order is a change detector.
   [ch. 12, ch. 13]
3. **Unchanging.** A test changes only when the behaviour it pins changes. Refactors, moves,
   renames and tier changes leave assertions word for word. [ch. 12]
4. **DAMP, not DRY.** A reader understands the test from its body; helpers build data, they do
   not hide the assertion. No logic in tests: no branches, no loops around asserts, no
   computed expectations. Expected values are literals or hand-checked fixtures. [ch. 12;
   `testing.md`]
5. **Real implementations first; fakes owned by the real implementation's owner; mocks last.**
   Mock only what is slow, external or unavailable on the host. [ch. 13]
6. **A reproduction is not a regression test.** The repro proves the fix once at full weight;
   the test that stays is the smallest one that still fails on the original bug, found by
   running against the parent of the fixing commit. [inference from Google ch. 14 and the
   minimisation literature]
7. **Change detectors are deleted or rewritten** to assert the behaviour that depends on the
   decision. A test that only an intentional change can fail (exact wording, a constant, a
   private structure, README prose) protects nothing. [Google ToTT 2015]
8. **Traceability by marker, not by layout.** `@pytest.mark.ticket("KEY")` on the test; the
   file is named for the module. A file with sections headed by ticket keys is a ledger, not
   a suite. [this harness's audit, 2026-10-20]

## 4. The smell catalogue, with the remedy you apply

Smells with measured harm come first [Bavota 2012: comprehension drops; Spadini 2018: code
tested by smelly tests 71 % more likely defective; PyNose 2021 for Python].

| Smell | You see | Remedy (changes no assertion unless noted) |
|---|---|---|
| Eager test | several behaviours, several "and"s in the name | split: one behaviour per test |
| Assertion roulette | several asserts, no messages | one assert per behaviour, or a message per assert |
| Mystery guest | the test depends on a file, env var or fixture the reader cannot see | inline the data, or name the builder that makes it visible |
| General fixture | a fixture far bigger than the test needs | minimal fresh fixture; builders with named variants |
| Conditional logic | `if`/`for`/`try` around asserts | parametrize, or split |
| Unknown test | asserts nothing (runs for coverage) | add the assertion the behaviour implies, or retire (needs a ledger line) |
| Magic number | an expectation computed by the code under test, or unexplained | a literal with its meaning in the name or a comment (changes the expectation's *form*, never its value) |
| Shared mutable fixture / test run war | tests pass alone, fail together or in another order | scope by mutability (§5); never pin order |
| Resource leak | processes, ports, temp dirs outlive the test | process-tree teardown; the session-end leak check fails the run |
| Sleepy test | `sleep(n)` waits for a condition | poll with a deadline; sleeps never fully fix flakiness [Luo 2014] |
| Slow test in `fast` | > 1 s, or any I/O | the contract: it is `heavy` |

## 5. The infrastructure tests run on

Most compute is before the assertion. Four levers; measure each before and after
[Meszaros: Shared Fixture, Lazy Setup, Creation Method, Test Data Builder; SWE at Google
ch. 12: test infrastructure has its own tests].

| Lever | Pattern | Rule |
|---|---|---|
| Imports | heavy libraries imported inside the tests or fixtures that need them; `-p no:` for unused plugins; `norecursedirs`, `testpaths` | a `fast` file imports nothing heavy at module level; every xdist worker pays every module-level import |
| Fixtures | **template and copy**: expensive immutable state built once per session, copied per test (`copytree`, `git clone --shared`, a store snapshot); **builders** for variants (`repo(with="epic,two-tickets,red")`); layered `conftest.py` (root: primitives; per directory: that domain's builders); in-memory stand-ins where the backend adds nothing | a test body does no setup a template, builder or session fixture could have done once; scope by mutability: session for what no test mutates, function copies for the rest |
| Processes | one long-lived server per session with per-test namespaces; `xdist_group` + `loadgroup` to pin tests that share a live fixture to one worker; `--dist loadfile` by default | nothing that spawns is unmarked; the process tree is killed by the harness, never trusted to the test |
| Cross-run | `--lf` / `--ff` for an owner's loop; dependency directories linked when the lockfile is unchanged; generated data cached under `.work/cache/` by content hash | a fresh worktree never rebuilds what a hash says is unchanged |

The layer lives under `tests/_fixtures/` with a README listing each builder, its one-time and
per-copy cost, and the tiers that may use it. It has its own `fast` tests: a copy is
independent of its template; a builder's variants are what they claim.

## 6. Flakes and quarantine

- **One classifying rerun**, fresh process, shuffled order. Pass on rerun = `FLAKY`, recorded
  with both outputs, never green. A second failure is red and you find the cause. Never a
  loop. [Gruber 2021: one rerun classifies, ~170 certify; Bazel reports FLAKY not PASSED]
- **Order dependence is the common Python flake** (59 %); fix it at the shared state.
  Infrastructure (28 %) is the next: a port, a leaked process, a loaded host. [Gruber 2021]
- **Quarantine has a cap**: about 8 tests or 7 days [Fowler 2011]; the owner acknowledges
  within 48 h; re-admission after 100 consecutive passes [GitLab; Uber]. A quarantined test
  runs in `heavy`, never on the merge path. Past the cap, it is retired with a ledger line.
- **Timeouts come from the tier, not from load.** Inflating a timeout for a loaded host hides
  contention and holds memory longer [Silva 2023: 46.5 % of flaky failures are
  resource-affected; CPU starvation dominant]. The fix is admission (memory budget, fewer
  workers), not a longer wait.
- **Load-induced reds are not flakes.** A whole-host burst of failures is infrastructure;
  scattered single failures are flakes. Classify before you act.

## 7. Verdicts: promote, rewrite, retire

After each wave, for every test under `tests/acceptance/<KEY>/`:

| Verdict | When | What you produce |
|---|---|---|
| **promote** | fits a tier's contract as written; pins an invariant no CI test pins; passes §3 | `git mv` into the module's file, tier marker, `ticket` marker, `ported-from` line |
| **rewrite** | pins something durable but at the wrong cost or shape (a full repro, an eager test, a general fixture) | the minimal test in the right tier; the original demoted or dropped; the **mutation bar**: every mutant the original killed, the rewrite kills (one sampled mutant per covered line, arid lines excluded) [Google 2018/2021; ACH 2025: coverage filters lose 49 % of useful tests] |
| **retire** | proved the ticket once and pins nothing durable; a change detector; a harness assertion that becomes a lint; a duplicate (the kept test kills every mutant it killed) | a ledger line with the replacement, rule or mutation diff; **never retire on coverage alone** [Yoo & Harman: > 50 % fault loss in half the suites] |

Each verdict is one line, `VERDICT <KEY> <test id> <verdict> <tier> — <why, citing a section
here>`, in the review packet and the PR body. Coverage per module may not drop; that is the
floor, never the oracle [Inozemtseva & Holmes 2014].

## 8. Acceptance tests: the three-state grade

A new acceptance test is accepted only at grade 2 [SWE-Cycle 2026; SWE-bench FAIL_TO_PASS]:

- **0**: passes on the pre-change code — it tests nothing new;
- **1**: fails on the pre-change code for an imprecise reason (ImportError, a missing stub,
  a collection error) — it may be testing the existence of a symbol, not a behaviour;
- **2**: fails on the pre-change code for the stated reason, passes after.

The test-designer writes to the quarantine and the owner cannot edit it; you are the third
reader. A test that passes its own implementation trivially is the documented failure mode
when one agent writes both [SWE-Cycle: 815 degradations vs 177 improvements].

## 9. What leaves the suite

Architectural checks are fitness functions with a tolerated range and an action, not
behaviour tests [Ford, Parsons & Kua]:

| Check | Where it goes |
|---|---|
| import layering, forbidden dependencies | an import-linter contract, run as lint |
| config shape, file layout, "X is gone" | `tests/architecture/`, milliseconds, part of `fast`, always run |
| README or doc prose | a docs build check, or deletion: it is a change detector |
| "the lockfile declares Y" | the dependency tool's own check (`uv lock --check`), in Lint |

## 10. Per wave

1. Read the packet, each landed ticket's diff, its reference, its quarantine, `gates.jsonl`,
   `tests/MAP.md`, `flakes.md`.
2. Grade each acceptance test (§8), then give its verdict (§7). Apply §3 and §4 to what you
   promote.
3. Look at the infrastructure the wave added (§5): a new fixture that should be a builder, a
   heavy import in a fast file, a server started per test. Fix within your ticket.
4. Check the budgets: a tier over budget, a test above 85 % of its kill, a flake past its cap.
5. Update `tests/MAP.md`, `tests/_fixtures/README.md`, the tiers in `config.md`.
6. Land as `<EPIC>-suite-<n>` through the normal gate (fast and heavy before landing, since
   you change what everyone depends on). Report the verdict lines and the metric trends (§1).

## 11. Adding a rule

A rule you add to `rules/` names its **warrant**: the failing episode or the source that
justifies it. Rules the agents already follow are pruned, not kept [Phantom Guardrails 2026:
rules without a warrant accumulate; Claude Code guidance: "delete it or convert it to a hook"].
A rule that can fail a change is a check script; prose is for what no check can express.
