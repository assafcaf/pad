# Handoff to PAD: the suite is a ledger, and the harness runs it as if it were free

From: a reasoning session with the operator, 2026-10-20, for the next `/spec grill` on PAD.
Baseline: PAD `main` at `28cab2e` (E2 merged: merge strategies, `affected` gate, suite slots,
flake record). Rollout-Collection (RC) at `94607b7`, on PAD 0.4.0.
Sources: `RC/.work/handoffs/2026-10-20-pad-from-kan136-kan164.md` (the evidence handoff, "EH"
below), a read of RC's `tests/` tree, and PAD's own scripts, agents and rules at `28cab2e`.

**The bottom line.** Two things compound. The RC suite is a ledger of ticket acceptance
evidence: 283 ticket references, one tier, no cost vocabulary, outcome pins that launch whole
sweeps. And PAD has no entity that owns that suite as a repo asset, no way to run a test except
"whatever is in `tests/`", and no notion of how much a test costs. So every role re-ran the same
heavy files, the gates ran nearly all of them, and the host collapsed. E2 fixed the merge
*queue*; this handoff fixes what runs, who decides, and how much it may cost.

Three units, in dependency order: **U1** a test wrapper that is the only way to run tests;
**U2** cost tiers with a latency budget and a merge path that keeps heavy tests off it;
**U3** a suite owner and a quarantine, so acceptance tests stop becoming CI by default.
Plus **U4**, the bootstrap epic on RC that U3 needs to exist before it can maintain anything,
and **U5**, added after the research pass: the per-repo test regime (manifest, rule kinds,
runner plugin, protected surface) that makes U1–U3 enforceable and lets each repo add its own
rules. §3a lists the corrections the research made to U1–U3. Companion files:
`reports/Test suite design standards.md` (the standard, ~150 sources) and
`suite-bootstrap.md` v2 (the first run of the suite owner on any repo).

---

## 1. Findings

Every issue found this session, with the evidence and the unit that fixes it. The letter says
where it came from: **E** the evidence handoff, **R** the RC suite audit, **P** PAD's source.

### 1a. How tests were run

| # | Finding | Evidence | Fix |
|---|---|---|---|
| F1 | Every role re-runs the same heavy files. Nothing counts invocations or refuses a repeat | **E** 223 min of agent calls ≈ 31 serial passes over the seven heavy files; KAN-155 ran pytest 64 times (106 min); six `for i in …; do pytest` loops cost 37 min | U1 |
| F2 | Gates run nearly the whole suite. `affected-tests.sh` matches import *names* as words and "over-selects, never under-selects"; on a dense fixture graph that is the full suite | **E** 65 of 73 files selected in 4 of 6 logged gates; KAN-148 (docs only) selected 65/73. **P** `affected-tests.sh` header | U2 |
| F3 | Contention multiplies wall time 3–4×, then timeouts tuned "for a loaded host" hold memory longer, which is more contention | **E** `test_store_race` 286 s vs 81 s quiet; KAN-138's gate 61 min then rejected; `RUN_TIMEOUT` 600–1200 s | U1, U4 |
| F4 | xdist's default `--dist load` rebuilds module fixtures per worker: 3.3× memory. PAD sets `-n {workers}` and never `--dist` | **E** 7.0 → 2.1 GB, 44 → 20 processes with `loadfile`. **P** `config.example.md` "Test workers" | U1 |
| F5 | Process-spawning tests run *inside* xdist workers | **E** `test_store_race` at `-n 4` = 8.1 GB of 13.5 GB; two such runs exceed the host | U1, U4 |
| F6 | Leaked and orphaned processes accumulate; the low-memory reaper kills only the wrapper shell | **E** 56 orphans + 6 `mlflow server` ≈ 9 GB; `OpenBLAS: Memory allocation failed`; 4 reaped merges | U1 |
| F7 | `verify-red.sh` is handed whole files, not node ids | **E** heavy files named 12 times by verify-red | U1 |
| F8 | No record of what each gate ran, so waste is invisible until someone mines transcripts | **E** this handoff needed 400 extracted runs to see it | U1 |
| F9 | Suite slots count runs, not memory, and only wrap the merge gate. Owners' and test-designers' runs take no slot; the config tells the operator to "size it so a gate plus the agents' named-test runs fit in RAM" | **P** `suite-slot.sh`, `merge-gate.sh`, `config.example.md` "Suite slots", "Test workers" | U1 |
| F10 | The `no-full-suite-in-agents` rule bans the *full suite* but not whole heavy files, so owners ran them as "named tests" | **E** owners 27× on `test_parallel.py`, 16× on `test_e2e.py`. **P** `rules/no-full-suite-in-agents.md`, `owner.md` step 3 | U1, U2 |
| F11 | One `Test workers` number serves the gate and every agent run alike | **P** `config.example.md`: "`merge-task.sh --workers` fills `{workers}` in the Full suite and Run named tests commands" | U1 |

### 1b. What the suite is

| # | Finding | Evidence | Fix |
|---|---|---|---|
| F12 | The suite is organised by ticket, not by module. A behaviour is tested in several places written in several epics; nobody can tell which are redundant | **R** 283 `KAN-` references across 79 tickets; `test_logging.py` is 3984 lines / 133 tests in 16 sections headed by ticket number (`KAN-34`, `KAN-36`, `KAN-25`, `KAN-37`, `KAN-35`, `KAN-44`, `KAN-39`, `KAN-38`, "KAN-38 falsifier round", `KAN-102`) | U3, U4 |
| F13 | No cost vocabulary. A gate cannot select by cost because cost is expressed nowhere | **R** 0 `slow`/`heavy`/`integration` markers; `[tool.pytest.ini_options]` is `testpaths` only; no `pytest-xdist` or `pytest-timeout` in `uv.lock` | U2, U4 |
| F14 | Outcome pins run the whole system. Right for closing an outcome once; wrong on every merge | **R** `test_e2e`, `test_sweep`, `test_parallel` each launch a full sweep in a fresh Python, module-scoped, one sweep per file; `test_e2e`/`test_main`/`test_smoke_server` build 4 smoke sweeps for 16 tests (**E** §3 RC-2) | U2, U4 |
| F15 | Reproductions kept at full weight. A repro proves a fix once; the regression test for it should be the minimal one | **R** `test_store_race.py`: 12 spawned processes each importing MLflow, for one assertion; "KAN-38, falsifier round: four reproductions" | U3, U4 |
| F16 | Harness assertions live in the product suite forever: tests of README sentences, decision files, `git ls-files`, `uv.lock` contents | **R** `test_docs.py`, `test_docs_layout.py`, `test_repo_layout.py`, `test_dependencies.py`, `test_lab_dependencies.py` | U3, U4 |
| F17 | A fast tier already exists but has no name and no gate of its own | **R** `test_config`, `test_health`, `test_task_registry`, `test_manifest`: pure logic against fabricated probe output, seconds each | U2, U4 |

### 1c. What the harness lacks

| # | Finding | Evidence | Fix |
|---|---|---|---|
| F18 | A test has two states, permanent or dev. There is no state for "proved the ticket; not yet decided for CI". `testing.md`: permanent tests "merge and stay" | **P** `testing.md` "Permanent and development tests"; `dev-tests-stay-out` rule | U3 |
| F19 | No role owns `tests/` as a repo asset. `test-designer` owns one ticket's oracle; `memory-curator` curates memory. TDD stands in for review, so test *design* is never reviewed: tier, cost, duplication, placement | **P** `config.example.md` "Agents"; `owner.md`, `test-designer.md` | U3 |
| F20 | No gate has a latency budget. `batch` spreads the heavy floor across tickets but the floor stays on the merge path, and heavy tests run *before* landing | **P** `merge-strategies/batch.md`; decision 0006 | U2 |
| F21 | Owners rebase and re-gate whenever the epic head moved, overlap or not; `merge-candidate.sh` already merges branches, so a clean merge needs no owner rebase | **P** `owner.md` step 7; "After READY" | U2 |
| F22 | Evidence and run stats carry shas and commands, not cost | **P** `config.example.md` "Tracker updates"; `run-stats.sh` | U1 |
| F23 | The epic's definition of done requires "the full suite and lint pass"; nothing requires that acceptance tests were triaged | **P** `definition-of-done.md` "An epic is done when" | U3 |
| F24 | The brief tells an owner the commands, not which existing tests its ticket is expected to touch | **P** `brief-template.md` "Gates" | U3 |
| F25 | No role owns the test *infrastructure* (templates, builders, shared servers, import cost), so setup is repeated per test: four smoke sweeps for 16 tests (F14); MLflow imported by 32 spawned processes (F5). The suite owner's expertise must cover the infrastructure tests run on, not only the tests | **R** `tests/experiments/safe/`, `tests/lab/` | U3 (`suite-design.md`, fixture layer), U4 |

---

## 2. Design

### U1. `pad-test.sh`: the only way to run tests

One script every role calls; raw runner invocations are denied in `settings.json`. The rules
U1 enforces are the ones prompts currently state and agents break under pressure.

```
pad-test.sh --run <id> --ticket <KEY> --role owner|test-designer|gate|suite-owner
            (--tier fast|heavy|epic | --ids <node id...> | --acceptance <KEY>)
            [--workers n] [--dist loadfile|loadgroup|load] [--timeout-mult 3]
```

| Behaviour | Detail | Fixes |
|---|---|---|
| Selection by tier or node id, never by file | `--ids` takes node ids; `--tier` resolves the config's selector; a bare file path is a usage error (exit 64) | F7, F10 |
| `--dist loadfile` by default | From `Dist:` in the config; `load` must be asked for | F4 |
| Memory admission, not slot counting | Reads `Memory budget: <GB>` (config) and the tier's `Declared GB` (config, or the last recorded `peak` for this selection in `gates.jsonl`); waits on `suite-slot.sh`, extended to take `--gb <n>` and admit while `sum(held) + n <= budget`. Every role's run is admitted; `--role gate` keeps merge priority | F5, F9, F11 |
| Own process group, killed on exit or signal | POSIX: `setsid` + kill the group; Windows: a job object via a small Python shim, or `taskkill /T /PID` by the recorded pid. `preflight.sh` and every `pad-test` start report orphaned test processes (by the marker env var `PAD_TEST_RUN=<id>`) and free memory | F6 |
| Repeat refusal | The same selection by the same ticket is admitted at most `Repeat limit: 3` times per run; the fourth prints `REPEAT <selection>: record a flake (`merge-gate.sh --run` flake file) or change the selection` and exits 65. No flag disables it | F1 |
| Timeout multiplier | Passes `--timeout=<quiet cost × mult>` using the tier's recorded wall per test when `pytest-timeout` is present; `Timeout mult: 3` in config | F3 |
| Records every run | Appends to `.work/runs/<id>/gates.jsonl`: `{role, ticket, selection, selected n/N, heavy k, workers, dist, wall s, peak GB, exit}`; `merge-task.sh` copies the gate's line into the ticket's evidence; `run-stats.sh` sums per role | F8, F22 |
| Workers per role | `Test workers` becomes a per-role row: gate, agent, suite-owner | F11 |

`settings.json` (shipped, merged by `/setup-workflow` with approval): deny
`Bash(pytest*)`, `Bash(python -m pytest*)`, `Bash(uv run pytest*)`, `Bash(* pytest *)`; allow
`Bash(bash .claude/workflow/bin/pad-test.sh*)`. `check-moves.sh` gains the pair as a capability
row so a repo on another runner proves its own deny/allow.

### U2. Tiers, a latency budget, and heavy tests after landing

```markdown
## Test tiers            (config.md, new section; `Tiers: none` reproduces today's gate)
| Tier  | Selector            | Budget | Declared GB | Runs                                   |
|-------|---------------------|--------|-------------|----------------------------------------|
| fast  | `-m "not heavy and not epic"` | 120 s | 4  | owner before READY; every batch, before landing |
| heavy | `-m heavy`          | 720 s  | 8           | once per landed batch, after landing   |
| epic  | `-m epic`           | none   | 8           | once, at the epic head, before the PR  |
```

| Change | Where | Detail | Fixes |
|---|---|---|---|
| Gate by tier | `merge-gate.sh --gate fast\|heavy\|epic` (keeps `full`, `affected`, `lint`) | Runs through `pad-test.sh --role gate --tier`; fails with `GATE OVER-BUDGET <tier> <wall>` when a tier exceeds its budget, which is the suite owner's signal, not the ticket's fault (the ticket is still landed when green) | F2, F13, F20 |
| Fast before landing, heavy after | `merge-strategies/batch.sh`, `single.sh` | Phase 1: candidate gated on fast + the batch tickets' acceptance tests (`tests/acceptance/<KEY>/` for each KEY in the batch). Green: land through `merge-task.sh --expect-tree` as today. Phase 2, after landing: `heavy` once on the new epic head, in the background, next pass not blocked. Red: bisect the landed prefix by `revert-merge` (a Git move that exists) of the first failing ticket, `REJECTED <KEY>: heavy gate ...`, requeue the rest; `GATE FLAKE` behaves as today | F14, F20 |
| `affected` demoted to fallback | `config.example.md` "Gate" | `Gate: tiers` is the default when `## Test tiers` is filled; `affected` and `full` remain for repos with `Tiers: none`. The selector's "over-selects, never under-selects" stance stays documented as the reason it is not the default | F2 |
| Rebase only on conflict | `owner.md` step 7, "After READY"; `merge-task.sh` | Step 7 becomes: read the channel; submit check; report `READY`. `merge-candidate.sh` merges the branch; only `CONFLICT` sends the owner back to rebase. `task-submit.sh`'s `missing-epic-head` must accept the epic head the ticket branched from, not the current one: verify this rule before changing the step | F21 |
| Epic gate | `pad-run` §4 step 1; `definition-of-done.md` | "Full gates at the epic head" becomes fast + heavy + epic tiers, each through `pad-test`, plus lint and typecheck | F20 |
| `no-full-suite-in-agents` rewritten | `rules/tests-through-pad-test.md` (replaces it) | "Agents run tests only through `pad-test.sh`, by node id or by the `fast` tier, at most once each before `READY`. The merge gate runs the tiers." Keep the KAN-107 and KAN-136 numbers as the rationale | F10 |

### U3. The suite owner and the quarantine

**The seam.** A ticket's tests prove the ticket; the suite proves the repo stays safe to merge
into, within budget. Today the first becomes the second by default. U3 inserts a decision.

| Piece | Detail | Fixes |
|---|---|---|
| Quarantine `tests/acceptance/<KEY>/` | Owners and test-designers write tests **only** there (plus stubs in their owned source files). The red commit, `verify-red.sh`, the owner's pre-READY run and the batch gate all use it. It is committed and lands with the ticket | F18 |
| Submit rule `tests-in-quarantine` | `task-submit.sh`: a changed path under the test paths outside `tests/acceptance/<KEY>/` fails `tests-in-quarantine: <path>` unless the ticket's owner role is `suite-owner`. Replaces the "test-path file the red commit added" exemption in the ownership rule | F18, F19 |
| The standard `workflow/suite-design.md` (new, shipped) | **The suite owner's expertise, as a file it reads on every start**, the way `test-designer` reads `testing.md`. Distilled from `reports/Test suite design standards.md`; every rule carries its source. Sections: mandate and metrics; tier contracts; test design rules (behaviours via public APIs, state not interactions, DAMP, unchanging tests, one behaviour per test, literal expectations, no logic in tests); the smell catalogue with remedies; fixture and import architecture (the four compute levers, template-and-copy, builders, scope by mutability); flake policy and quarantine; the verdict rubric (promote / rewrite / retire, with the mutation bar); the acceptance three-state grade; what leaves the suite (fitness functions); the per-wave procedure; the rule for adding rules (warrant required). `/pad-update` replaces it; a repo adds to it through plugins and rules, never by editing it. The bootstrap prompt is this standard applied once to an existing suite | F12, F15, F19, F25 |
| Agent `suite-owner` | `agents/suite-owner.md`: `isolation: worktree`, `memory: project`, model `sonnet`. **Reads `suite-design.md` first and applies it**; its report cites the section behind each verdict. Owns `tests/**` except the quarantine dirs of in-flight tickets; the one role allowed to write outside quarantine. Mandate: the repo stays safe to merge into within the tiers' budgets. Inputs: the wave's review packet, each landed ticket's diff, scope reference and `tests/acceptance/<KEY>/`, `gates.jsonl`, and `tests/MAP.md`. Outputs: one ticket `<EPIC>-suite-<n>` per wave with a diff on `tests/`, a verdict per acceptance test, an updated map and tiers | F12, F15, F16, F19 |
| Three verdicts | **promote** (moves as is into a tier, by module, with a `ported-from` marker), **rewrite** (a minimal in-process regression test in `fast`; the original reproduction demoted to `heavy` or `epic`, or dropped), **retire** (proved the ticket once; proves nothing durable). Each is a line `VERDICT <KEY> <test id> promote\|rewrite\|retire <tier> — <why>` in the review packet and the PR body | F12, F15 |
| Removal rule `drained-by-suite-owner` | `rules/drained-by-suite-owner.{md,sh}`: a removed test under `tests/acceptance/` is explained when the removing commit's ticket is a suite ticket and a `VERDICT` line names it. `weakened-tests.sh` runs it like the others; nothing is switched off | F18 |
| Harness assertions leave the suite | Tests of docs text, repo layout, lockfile contents become a submit-time lint: `rules/` entries with `.sh` checks (`scope-docs-updated`, `layout-as-declared`), run by `task-submit.sh`'s test-authoring pass. The suite owner's first verdict on such a test is `retire` with the rule that replaces it | F16 |
| Fixture and import layer `tests/_fixtures/` | The suite owner owns the four compute levers, not only the tiers: **imports** (heavy libraries inside the tests that need them, never at module level of a `fast` file; `-p no:` for unused plugins; `norecursedirs`), **fixtures** (layered conftest; template-and-copy for expensive immutable state, built once per session and copied per test; builders for per-test variants so a test body runs zero setup commands; in-memory stand-ins), **processes** (one long-lived server per session with per-test namespaces; `xdist_group` + `loadgroup` to pin tests sharing a live fixture), **cross-run** (`--lf` for owners' loops; linked deps; generated data cached under `.work/cache/` by content hash). The layer has its own `fast` tests and a README listing each builder's one-time and per-copy cost. Measured in `gates.jsonl` as collection seconds, fixture setups per run, setup commands inside test bodies | F5, F14, F25 |
| `tests/MAP.md` | Maintained by the suite owner: module → test files → tier, plus the invariants each module's tests pin. `pad-run` writes two lines per ticket into the brief from it, by script (`brief-tests.sh <ticket> → "Expected to touch: <files>" · "Before READY: pad-test --tier fast --ids <acceptance>"`), so the per-wave agent cost stays one dispatch | F24 |
| When it runs | After each wave's review, as its own ticket, **in parallel with the next wave**: nothing else writes `tests/` outside quarantine, so there is no overlap by construction. Its ticket is the exception to "heavy after": it changes the fast tier everyone depends on, so it runs fast and heavy before landing, and it is the one ticket whose landing can trigger a rebase in a wave with no file overlap (owners whose brief names a test it changed) | F19, F21 |
| Epic done | `definition-of-done.md` adds: `tests/acceptance/` is empty at the epic head; every acceptance test has a `VERDICT`; the epic tier is green. `pad-run` §4 runs the last suite ticket before the epic gate | F23 |
| `testing.md` | New section "Three states": acceptance (quarantine, per ticket), CI (tiered, suite owner's), dev (never committed). "Permanent tests … merge and stay" is replaced | F18 |
| `memory-curator` unchanged | Memory and tests are different assets with different owners | — |

**Bootstrap.** `Tiers: none` keeps every current behaviour, so a project that has not adopted
tiers still runs. A project adopts them with one epic whose only owner is the suite owner (U4
for RC). `/setup-workflow` gains a step that offers it when `tests/` exists and no tiers are
configured.

### U4. The RC bootstrap epic (a ticket for RC, listed here because the session found it)

Run once, by the suite owner, before any feature epic uses U2 on RC. Order matters: measure,
then tier, then consolidate, then retire with evidence.

| # | Change | Evidence |
|---|---|---|
| 1 | Inventory from `--durations=0` and `measure.jsonl` (EH §1): every file's wall and peak; the module → tests map; the invariant each module's tests pin | F13, F17 |
| 2 | `pyproject.toml`: `pytest-xdist`, `pytest-timeout`; `addopts = "--dist loadfile --timeout=<3× quiet>"`; markers `heavy`, `epic` (EH RC-3, RC-4) | F3, F4, F13 |
| 3 | Fast tier, by module, in-process: what `test_config`, `test_health`, `test_task_registry`, `test_manifest` already are; `test_logging.py` split into `test_selector.py`, `test_sink.py`, `test_publishing.py`, duplicates merged, each file a module not a ticket | F12, F17 |
| 4 | Heavy tier from the outcome pins: one session-scoped smoke sweep shared by `test_e2e`, `test_main`, `test_smoke_server` (EH RC-2); `test_parallel` and `test_sweep` keep one sweep each; all marked `heavy` | F14 |
| 5 | `test_store_race`: 2 workers in `fast`, 12 in `heavy`, the 32-process case `epic` (EH RC-1) | F5, F15 |
| 6 | Session-end conftest check that fails the run when a process started under the test tree is still alive (EH RC-5) | F6 |
| 7 | `test_docs`, `test_docs_layout`, `test_repo_layout`, `test_dependencies`, `test_lab_dependencies` → retired, replaced by PAD submit lints (U3) | F16 |
| 8 | Retire ticket-shaped duplicates only when the coverage diff (`pytest --cov` before and after, per module) shows the replacement covers the same lines; the diff is the ticket's evidence | F12 |
| 9 | `tests/MAP.md` written; `## Test tiers` filled in RC's `config.md` with measured budgets | F13, F24 |
| 10 | Fixture layer `tests/_fixtures/`: one session-built smoke sweep copied per test; a populated MLflow store as a template; `make_published_runs` behind a builder; MLflow and torch imported inside the heavy tests only; a shared `mlflow server` per session for the report-UI tests | F5, F14, F25 |

### U5. The test regime is per-repo: manifest, rules, plugins, on a protected surface

Added after the research pass (`reports/Test suite design standards.md`, 2026-10-20). Every
repo has testing rules nobody else has: a GPU box only one tier may use, a simulator fixture
that must be shared, a port that must stay free, a domain check that runs before `READY`. The
research is unanimous that such rules work only as **exit-nonzero configuration agents cannot
edit**, never as prose: Claude Code's own docs ("hooks are deterministic, CLAUDE.md is
advisory"), pre-commit's pinned-rev contract, Bazel's sandbox-enforced tags, and the 2026
BenchJack result that an agent-added `conftest.py` can mark every test passed.

PAD already has the two halves of this: **rules** (`rules/`, a Markdown file plus an optional
check script, enforced at one point per kind, validated by `rules.sh validate`, decision 0004)
and **plugins** (`.claude/pad-plugins/`, prose additions read by named agents, decision 0003).
U5 extends both and adds the thing neither has: a declarative manifest and a protected surface.
No third mechanism.

```
                 declares                enforces                     guides
config.md  ──►  ## Test regime   ──►  pad-test.sh + runner plugin  ──►  brief lines (derived)
rules/     ──►  <name>.md + .sh  ──►  one enforcement point per kind
pad-plugins/ ─► <name>.md        ──►  steps a named agent carries out (suite-owner, test-designer)
```

| Piece | What it is | Merge semantics | Validated by | Can fail a change |
|---|---|---|---|---|
| `## Test regime` (config.md, new section) | The repo's manifest: tiers (from U2), `Allowed hosts` per tier, `Named resources` (`gpu`, `sim`, `port:5555`) with the tier that may use them and the Serial-resource class they map to, `Always run` (test ids every gate runs regardless of selection), `Quarantine cap` (count and days), `Rerun policy` (fixed: one classifying rerun), `Protected surface` (managed list + repo additions) | Managed defaults + repo additions; **a repo key may add, never remove or relax a managed value**; `preflight.sh` fails a manifest that tries | `preflight.sh`; `pad-test.sh --validate` collects with the manifest applied | yes, through the gate it configures |
| Rule kinds, extended (`rules.sh`) | `test-authoring` and `test-removal` as today; new **`tier-contract`** (what a tier's tests may touch; the check is a runner-side hook, see below), **`suite-structure`** (layout contracts: file-per-module, marker required under a path, no test outside `tests/`, import layering via an import-linter contract), **`acceptance`** (the three-state bar for a new acceptance test: fails on pre-change code for a precise reason, passes after). Every rule gains a required `warrant:` field naming the episode or source that justifies it | Additive; a repo adds files beside PAD's; `/pad-update` never touches a repo's | `rules.sh validate` (kind has an enforcement point, check exists, `warrant` present) | yes: `tier-contract` in the runner, `suite-structure` and `acceptance` in `task-submit.sh`, the others as today |
| PAD runner plugin (`tests/_pad/pad_plugin.py`, shipped; pytest first) | Loaded by `pad-test.sh` with `-p`, never by `conftest.py`. Registers markers, `--strict-markers`, socket policy per tier (pytest-socket with the manifest's hosts), subprocess and `multiprocessing` block for `fast`, must-assert and no-conditional-logic collection checks, the `ticket("KEY")` marker, the session-end leak check. Repo `tier-contract` rules add a hook module under `tests/_pad/rules/<name>.py` that the plugin loads by name | Additive hook chain (pytest's 1:N hooks); a repo hook cannot unregister a PAD check | `pad-test.sh --validate`: collection with every hook on, against an empty selection | yes |
| Plugin readers, extended (`plugins.md`) | `suite-owner` reads plugins that `Extends: suite-owner`: canonical fixtures, resources and what "heavy" means here, extra bootstrap-phase steps, domain checks per wave. `test-designer` reads plugins that extend it: the domain's reference data, fixtures it must use rather than rebuild. Both get `Bash` only for the scripts a listed plugin names, as `tracker` does today | Add, never override (decision 0003 unchanged) | `preflight.sh` plugins check | no (prose); the steps it names run scripts that can |
| Protected surface (managed `## Protected paths` entries) | `conftest.py` at any depth, the runner config section, `tests/_pad/**`, `tests/MAP.md`, CI workflow files, `.claude/workflow/**`, `.claude/settings.json`, `.pre-commit-config.yaml`. Managed entries cannot be removed by the repo; a diff there is accepted only from a suite-owner ticket, and `merge-task.sh --protected` rejects any other (`needs-suite-owner`) | Managed + repo additions | `preflight.sh`; `task-submit.sh` ownership rule | yes |
| Derived guidance | `brief-tests.sh` prints the manifest's tier contract and the ticket's expected tests into the brief; `tests/_pad/README.md` is generated from the manifest. Prose follows config, never the reverse | — | `knowledge-paths.sh`-style staleness check: README older than manifest fails preflight | no |

**Worked example, Rollout-Collection:**

```markdown
## Test regime
Allowed hosts: heavy `127.0.0.1`; epic `127.0.0.1`
Named resources:
| Resource | Tier | Serial class | Free when |
|---|---|---|---|
| `gpu` | epic | operator-run | `nvidia-smi --query-gpu=memory.used` under 1 GB |
| `mlflow-store` | heavy, epic | automated | no `mlflow server` process alive |
Always run: tests/architecture/
Quarantine cap: 8 tests, 7 days; owner acknowledges within 48 h; re-admit after 100 consecutive passes
Protected surface: + `lab/conf/sweep.yaml`
```

Rules RC adds beside PAD's: `tier-contract/no-sweep-in-fast` (a `fast` test may not import
`lab.sweep.sweep_main`; hook module), `suite-structure/lab-tests-marked` (every file under
`tests/lab/` carries `heavy` or `epic`), `test-authoring/no-real-gpu` (an added test may not
call `torch.cuda` outside `epic`). Plugin `rc-suite.md`, `Extends: suite-owner`: the shared
smoke sweep is the canonical heavy fixture; `test_store_race` is the known 12-process case;
phase-5 addition: "the sim container is never started by a test; `probe_*` scripts under
`gates/` are the epic tier's operator-run outcomes."

**What this changes in the earlier units.** U1's `pad-test.sh` reads the manifest and loads the
runner plugin; U2's tiers table moves under `## Test regime`; U3's suite owner reads plugins
and is the only owner whose tickets may touch the protected surface; the bootstrap prompt
(`suite-bootstrap.md`, v2) writes the first manifest in its phase 3.

---

## 3. Changes per file in PAD

| File | Change | Findings |
|---|---|---|
| `bin/pad-test.sh` (new) | U1, as specified | F1, F3–F11, F22 (F5 through memory admission) |
| `bin/suite-slot.sh` | `--gb <n>`: admit by memory against `Memory budget:`; keep slot counting when the budget is unset | F9 |
| `bin/merge-gate.sh` | `--gate fast\|heavy\|epic`; runs through `pad-test.sh`; `GATE OVER-BUDGET`; copies the `gates.jsonl` line into evidence | F2, F8, F20 |
| `merge-strategies/batch.sh`, `single.sh`, their `.md` | Phase 1 fast + acceptance before landing; phase 2 heavy after, with revert-bisect; "when to use" text updated | F14, F20 |
| `bin/merge-task.sh` | Accept a ticket whose base is an older epic head when `merge-candidate.sh` merged it cleanly; evidence carries the gate line | F21, F22 |
| `bin/task-submit.sh` | Rule `tests-in-quarantine`; ownership rule's test-path exemption narrowed to the quarantine dir | F18, F19 |
| `bin/verify-red.sh` | Refuse a file path in the test command; node ids only (exit 64 with the node-id form) | F7 |
| `bin/weakened-tests.sh` | No change; the new rule plugs in through `rules.sh list test-removal` | — |
| `bin/preflight.sh` | Orphaned-test-process and free-memory report; validate `## Test tiers`; offer the bootstrap step | F6 |
| `bin/run-stats.sh` | Sum `gates.jsonl` per role: runs, wall, heavy passes, over-budget gates, repeats refused | F8, F22 |
| `bin/brief-tests.sh` (new) | Two brief lines per ticket from `tests/MAP.md` and the ticket's Owns | F24 |
| `bin/check-moves.sh` | Prove the `pad-test` allow and the runner deny rows | F10 |
| `rules/tests-through-pad-test.md` (replaces `no-full-suite-in-agents.md`) | As in U2 | F10 |
| `rules/drained-by-suite-owner.{md,sh}` (new) | Test-removal rule for quarantine drains | F18 |
| `rules/scope-docs-updated.{md,sh}`, `rules/layout-as-declared.{md,sh}` (new, repo-optional) | Submit lints that replace docs/layout tests | F16 |
| `workflow/suite-design.md` (new, shipped) | The suite owner's standard; drafted as `suite-design.md` in this handoff's companion files | F12, F15, F19, F25 |
| `agents/suite-owner.md` (new) | As in U3; reads `suite-design.md` on start; its first epic on a project is U4 | F12, F15, F16, F17, F19, F25 |
| `agents/owner.md` | Tests go in `tests/acceptance/<KEY>/`; step 3 and 4 run `pad-test --ids` / `--tier fast` once; step 7 rebases only on `CONFLICT`; "Never run the full suite" becomes "never run tests except through `pad-test`" | F1, F10, F18, F21 |
| `agents/test-designer.md` | Writes under `tests/acceptance/<KEY>/`; runs through `pad-test --ids`; its report's `OUTCOMES` lines are what the batch gate and the suite owner read | F7, F18 |
| `workflow/testing.md` | "Three states" section; "Pass under load" paragraph points at `pad-test` and the budget instead of asking tests to tolerate load | F3, F18 |
| `workflow/definition-of-done.md` | Epic: quarantine empty, every acceptance test has a verdict, epic tier green; merge gate: fast + acceptance | F23 |
| `workflow/brief-template.md` | "Gates" lists the `pad-test` forms; per-ticket "Expected to touch" / "Before READY" lines | F24 |
| `workflow/config.example.md` | `## Test tiers`; `Memory budget`, `Dist`, `Repeat limit`, `Timeout mult`; `Test workers` per role; `Gate: tiers` default; agents table gains `suite-owner` | F4, F9, F11, F13 |
| `skills/pad-run/SKILL.md` | §3: dispatch `<EPIC>-suite-<n>` after each review, parallel with the next wave; heavy phase results handled like merge results; §4: last suite ticket, then tiers at the epic head; PR body lists `VERDICT` lines and `run-stats` cost per role | F19, F20, F23 |
| `skills/setup-workflow/SKILL.md` | Detect xdist/timeout; write `Memory budget` from the host (free memory minus a desktop reserve); offer the bootstrap epic | F9, F13 |
| `payload/claude/settings.json` + `payload/migrations/0005-*.md` | Deny raw runner, allow `pad-test`; migration note for upgraded repos (tiers default to `none`) | F10 |
| `docs/decisions/0007-tiers-wrapper-suite-owner.md` | The decision, with this handoff's numbers | — |
| **U5 additions** | | |
| `workflow/config.example.md` | `## Test regime` section (manifest; the U2 tiers table moves under it); managed `## Protected paths` entries for the test-discovery surface | U5 |
| `bin/rules.sh` | Kinds `tier-contract`, `suite-structure`, `acceptance`; required `warrant:` field; `validate` checks each kind's enforcement point | U5 |
| `payload/tests/_pad/pad_plugin.py` (new, shipped into `tests/_pad/`) | PAD runner plugin: markers, strict markers, socket policy per tier from the manifest, subprocess/multiprocessing block for `fast`, must-assert and no-conditional-logic collection checks, `ticket()` marker, session-end leak check; loads repo hook modules named by `tier-contract` rules | U5, F4, F5, F6 |
| `bin/pad-test.sh` | Reads `## Test regime`; loads the plugin with `-p`; `--validate` mode; one classifying rerun in a fresh process with shuffled order, result `FLAKY` never green | U5, F1 |
| `bin/task-submit.sh` | Runs `suite-structure` and `acceptance` checks; `needs-suite-owner` for a diff on the protected surface from any other ticket | U5 |
| `bin/merge-task.sh` | `--protected` gains `needs-suite-owner` | U5 |
| `bin/preflight.sh` | Manifest validation (no managed value removed or relaxed); `tests/_pad/README.md` not older than the manifest | U5 |
| `bin/brief-tests.sh` | Also prints the tier contract from the manifest | U5 |
| `workflow/plugins.md` | Readers table: `suite-owner`, `test-designer` | U5 |
| `agents/suite-owner.md`, `agents/test-designer.md` | Read plugins that extend them; `Bash` only for listed scripts (as `tracker`) | U5 |
| `rules/` shipped | `must-assert`, `no-conditional-logic`, `no-skip-without-ticket`, `raises-needs-match` (`test-authoring`); `fast-no-io` (`tier-contract`); `file-per-module`, `marker-under-path` (`suite-structure`); `three-state-red` (`acceptance`); each with a `warrant:` citing the report | U5 |
| `payload/migrations/0006-test-regime.md` | Upgraded repos: manifest written from existing config; protected surface added; `Tiers: none` until the bootstrap runs | U5 |

## 3a. Corrections to U1–U3 from the research pass

The report (`reports/Test suite design standards.md`) confirms the units and sharpens five
details. Apply these over the text above where they differ.

| Where | Was | Now | Evidence |
|---|---|---|---|
| U1 repeat refusal | 4th identical run refused | **One classifying rerun**, in a fresh process with shuffled order, then stop. Pass on rerun = `FLAKY` in the run's flake record, never green. A third run is refused | Gruber 2021 (1 rerun classifies, ~170 certify); Google reruns only flaky-marked tests; Bazel reports `FLAKY`, not `PASSED` |
| U1 timeouts | `Timeout mult: 3` × recorded quiet cost | **Per-test kill fixed by tier**: 60 / 300 / 900 s (Bazel short/moderate/long). The watchdog is **outside** the test process, per shard, with process-group kill and a 10 s grace; on Windows a Job Object with `KILL_ON_JOB_CLOSE`. pytest-timeout's `thread` method is not a watchdog on Windows (hard exit, no teardown, no report) | Bazel test encyclopedia; nextest slow-test handling; pytest-timeout README |
| U2 tier definition | by measured cost | by **resource contract**, enforced in the runner (U5 plugin): `fast` = Feathers' five prohibitions (no socket, no subprocess, no sleep, no shared state, temp-dir FS only); `heavy` = one machine, localhost; `epic` = anything, exclusive. Cost follows from the contract | Google test sizes 2010, SWE at Google ch. 11; Feathers 2005 |
| U2 epic tier cadence | once at the epic head | **on a horizon**: every k landed batches or nightly, and at the epic head, so no test goes unrun longer than the horizon | THEO (Microsoft): every test runs at least every 3rd day; Facebook: full suite on master every few hours |
| U2 red batch | bisect by revert | **(1)** same-SHA rerun of the failing ids only, fresh process, shuffled; **(2)** rerun without the batch; **(3)** halve; **(4)** revert only when one ticket is isolated. Batch size 3–5 to start, grow while batch failure rate < 10 % | Google: 84 % of pass→fail transitions involve a flaky test; Chromium "fails-with / passes-without"; Trunk batching guidance |
| U3 rewrite / retire bar | coverage diff per module | **mutation diff**: one sampled mutant per covered line, arid lines excluded; every mutant the old test killed must die. Coverage is a floor, never the oracle | Yoo & Harman: coverage-based minimisation loses > 50 % of faults in half the suites; Google mutation 2018/2021; ACH 2025 |
| U3 quarantine | unspecified | hard cap: ~8 tests or 7 days; owner acknowledges within 48 h; re-admit after 100 consecutive passes; sleep-based fixes rejected by rule | Fowler 2011; GitLab handbook; Uber; Luo 2014 |
| U3 acceptance tests | red proven by `verify-red.sh` | **three-state grade** at submit: 0 = passes on pre-change code, 1 = fails imprecisely (ImportError, collection error), 2 = fails for the stated reason then passes. Only 2 is accepted | SWE-Cycle 2026 (815 degradations when one agent writes both); SWE-bench FAIL_TO_PASS protocol |
| U3 memory budget | a gate failure | a **scheduling** outcome: `pad-test` reports `OVER-BUDGET` as a harness event, not a test failure, until there is data; memory per tier is a first-of-kind control with no published enforcement precedent | Bazel's 20/100/300/800 MB are scheduling weights, not caps |

## 4. What is settled, and what the spec must still grill

Settled in the session (do not reopen):

- Quarantine over branch-only acceptance tests: simpler to script, leaves an audit trail.
- The suite owner is an **owner of a domain**, not a curator: it decides what the suite is.
  Its first run on a project is the from-scratch redesign.
- It runs once per wave, in parallel with the next wave, as a ticket through the normal gate.
- Heavy tests run after landing, once per batch; the epic tier once per epic.
- Enforcement is by script and settings (`pad-test`, deny rules, submit rules), never by a
  sentence in an agent prompt.
- `memory-curator` stays as it is.

Open, for `/spec grill`:

1. **Declared GB per tier vs measured.** Start from the config's number, replace it with the
   last recorded peak for the same selection once one exists? Or always the max of the two?
2. **Repeat limit semantics.** Per (ticket, selection) per run, or per role per ticket? The
   evidence (KAN-155: 64 runs across many selections) argues for a per-ticket total as well.
3. **Heavy-after bisection cost.** Reverting and re-gating heavy on a landed batch of 8 is up
   to 1 + log2(8) heavy runs. Cap the batch for heavy purposes (`heavy-max=4`)? Or accept and
   let `dynamic` back off to `single` on a heavy red, as it does on flakes?
4. **`task-submit.sh` `missing-epic-head`.** Confirm it can accept the branched-from head
   before dropping the owner's rebase; if not, keep the rebase but make it a `merge-task.sh`
   mechanical step, not an owner round.
5. **Windows process groups.** Job object via Python shim, or `taskkill /T` by pid? The shim is
   reliable; the taskkill form needs no interpreter. RC runs on Windows, so this is not optional.
6. **The suite owner's model.** `sonnet` like the others, or `opus` for the bootstrap epic
   only, where the redesign is the whole job?
7. **Where harness lints live.** As PAD-shipped rules (repo-optional), or as a project plugin
   under `.claude/pad-plugins/`? Rules can fail a submit; plugins only add steps.

## 5. How to check the numbers

- RC suite audit commands (run from RC's root): file sizes `find tests -name 'test_*.py' | xargs wc -l`;
  ticket references `grep -rhoE 'KAN-[0-9]+' tests --include='test_*.py' | sort -u | wc -l`;
  markers `grep -rhoE '@pytest\.mark\.[a-zA-Z_]+' tests | sort | uniq -c`; sections
  `grep -nE '^# ---' tests/test_logging.py`; plugins `grep -cE 'name = "pytest-(xdist|timeout)"' uv.lock`.
- Evidence handoff: `pad/.work/kan136-164/{measure.py,measure.jsonl,runs136.json,runs164.json,testload.py}`.
- PAD source at `28cab2e`: `payload/claude/workflow/bin/{suite-slot,merge-gate,affected-tests,verify-red,task-submit}.sh`
  headers; `payload/claude/agents/{owner,test-designer}.md`;
  `payload/claude/workflow/{testing,config.example,brief-template,definition-of-done}.md`;
  `payload/claude/workflow/rules/no-full-suite-in-agents.md`; `docs/decisions/0006-merge-strategies.md`.
- Success criteria for the first RC epic on U1–U3 (compare with EH §2): heavy passes per epic
  ≤ waves + 1; agent test runs per ticket ≤ 3; no gate over budget twice in a row; zero
  orphaned test processes at every `pad-test` start; merge wall per batch ≤ fast budget + landing.
