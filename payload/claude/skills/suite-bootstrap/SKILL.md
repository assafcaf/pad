---
name: suite-bootstrap
description: Bring a repository's existing test suite into the tiered regime, once, before its first epic that uses test tiers. Runs the bootstrap phases 0-8 as suite-owner subagents on opus, one per phase, handing off through .work/suite/, stops after phase 3 for the operator to review the configuration, and ends with a draft PR and a report block. Run as /suite-bootstrap; never start it unasked.
disable-model-invocation: true
---

# Suite bootstrap

Input: `$ARGUMENTS`. Read `.claude/workflow/config.md` (`## Test regime`, `## Commands`) and
`.claude/workflow/host.md`; if `host.md` is missing, run `/setup-workflow`'s host step first.

You are the orchestrator of one run: you dispatch, you do not do a phase yourself. The standard
the work applies is `.claude/workflow/suite-design.md`: **the suite owner reads
`suite-design.md` first**, before this skill's phases and before any handoff file. Each phase's
content is in [phases.md](phases.md), adapted from the bootstrap prompt (version 2).

## Before the first phase

1. **Claim the host exclusively.** Nothing else may run tests on this host while the bootstrap
   runs: no `/pad-run`, no other PAD run, no foreign test process. Stop with the list when
   a recorded run under `.work/runs/*/pad-test/` has no `.done` file, or
   `bash .claude/workflow/bin/pad-test.sh --sweep` reports a leftover. A phase's test runs
   declare the whole cap, so admission lets no other run in.
2. **Operator inputs.** Ask for the fast budget (seconds; default 180, never above 600) and the
   epic horizon (every k batches or nightly; default 3). The memory cap is not asked: it is
   `Memory cap` in `host.md`, and no memory figure is written to the config.
3. Create the branch `suite/bootstrap` from the default branch, and `.work/suite/` with the
   operator inputs in `.work/suite/inputs.md`.

## The phases

Dispatch `suite-owner` on opus (`model: opus`), **once per phase**, in order, each as a fresh
subagent named `suite-<phase>`. The brief to each is only: the phase number, the path of
`phases.md`, `.claude/workflow/suite-design.md` (read first), and `.work/suite/` for what the
earlier phases left. A phase reads its predecessors' files and writes its own; nothing is
carried in the dispatch message, so a phase can be rerun from its files.

| Phase | Does | Leaves in `.work/suite/` |
|---|---|---|
| Phase 0 | set up, read the host, prove it is quiet | `host.md` |
| Phase 1 | measure the suite as it is | `measure.jsonl`, `durations.txt` |
| Phase 2 | inventory what each test proves | `inventory.md` |
| Phase 3 | design the tiers, write the configuration (the reviewed commit) | the config's `## Test regime`, the runner contract, the protected surface |
| Phase 4 | build the fast tier by module | `coverage-before.txt`, `mutants-before.txt`, `REMOVALS.md` |
| Phase 4b | build the fixture and import layer | `tests/_fixtures/` and its README |
| Phase 5 | consolidate the heavy and epic tiers | tier measurements |
| Phase 6 | retire what the suite should not carry | `lints-needed.md`, `REMOVALS.md` |
| Phase 7 | verify | `coverage-after.txt`, `mutants-after.txt` |
| Phase 8 | leave the files the harness reads, open the draft PR | `tests/MAP.md`, the decision record |

Phase 4b runs after Phase 4 and before Phase 5. It builds the fixture and import layer under
`tests/_fixtures/`, with a `tests/_fixtures/README.md` that lists each builder's one-time and
per-copy cost and the tiers that may use it. The layer has its own `fast` tests: a copy is
independent of its template, a builder's variants are what they claim.

One commit per phase, subject `suite(bootstrap): phase <n> ...`; a phase reports its commit and
what it left, and you check the files exist before the next dispatch.

## Stop after phase 3

The bootstrap stops after Phase 3, for the operator's review: Phase 3 is the commit that changes
the runner configuration, the `conftest.py` files, the runner plugin and the protected surface.
Show the operator its diff and the tiers table, and end your turn. Continue to Phase 4 only on
the operator's word, and on their changes if they ask for any.

## Test runs

Every test run goes through `bash .claude/workflow/bin/pad-test.sh --role suite-owner ...`. Never
run the runner directly: not pytest, not vitest, not any adapter's command. `pad-test.sh`
admits the run under the memory cap, contains its processes, sweeps what a finished run left and
records the run; a phase that runs a test any other way has not been measured.

## The end

After Phase 8, push the branch and open a **draft PR** titled `Suite bootstrap: tiered test
suite`; do not merge it. Then print the **report block** and nothing after it:

```
SUITE BOOTSTRAP <repo> — branch suite/bootstrap, PR <url>
Before: <files> files, <tests> tests, full run <wall> s, peak <GB> GB, <n> ticket-shaped files, <n> harness files
After:  fast <tests> tests <wall> s / budget <s> · heavy <tests> <wall> s / budget <s> · epic <tests> <wall> s
        peak fast+heavy together <GB> GB / cap <GB> GB · leftover processes 0 · near-timeout 0
Coverage per module: no module lost lines | <module>: reverted <removal>
Mutation diff: <killed before> killed before, <killed after> after, surviving-that-were-killed 0 | <list>
Order independence: pass | <test ids>
Moved: <n> · merged: <n> · rewritten: <n> · retired: <n> (all in REMOVALS.md)
Infrastructure: collection <s> → <s> · fixture setups per run <n> → <n> · setup commands inside test bodies <n> → <n> · peak processes <n> → <n>
Seams added to production code: <path: what> | none
Lints PAD must add: <n> (lints-needed.md)
Flakes recorded: <n> (flakes.md), each placed in heavy
Open for the operator: <unclear tests, assertion changes you did not make, tests that fit no tier>
```
