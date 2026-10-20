# 0007. A test regime: a capped host, one test wrapper, cost tiers, and a protected surface

Date: 2026-10-20 · Status: accepted · Tracker: E3

## Context
Runs on the operator's machine exhausted its memory, left processes running, and let agents
run whole suites, each as often as they liked; acceptance tests written for one ticket became
the repo's CI by default. The cause was that PAD had no notion of what a test costs, who may
run one, or who owns the suite. A repo also had no way to say which of its files decide how
tests run, so any ticket could weaken them.

## Decision
- **The host is capped and contained.** The cap is whole-machine memory in use, 85% by
  default (an exact figure may be given; `/pad-run --cap` overrides it for one run), enforced
  by admission plus a watchdog that `/pad-run` starts and stops. Containment is a Windows job
  object (via PowerShell, with kill-on-close) or a POSIX process group, plus a sweep of
  recorded runs; it is self-tested at setup and again by `preflight.sh`, and a failed self-test
  stops setup with the reason. Admission estimates a run as the larger of its declared GB and
  the highest of the last 5 completed peaks.
- **Tests run through `pad-test.sh`, only.** Agents run no runner directly: the settings deny
  the adapter's `runner-names` and allow `pad-test.sh`, and `check-moves.sh` proves the pair.
  The runner is reached through an adapter, one per repo (PAD ships `pytest` and `vitest`); a
  runner without one gets an adapter written from `TEMPLATE.sh`, accepted only after its
  self-test passes. A required core plus declared extras; gaps are reported, not failed.
- **Cost tiers** fast, heavy and epic, with a per-test kill of 60 / 300 / 900 s. Limits: one
  classifying rerun per tree, 3 per selection and 12 per ticket on changed code; then
  failed-only until green, one wider run. Flaky quarantine is capped at 8 tests and 7 days; the
  owner acknowledges within 48 h; a test is re-admitted after 100 consecutive passes.
- **`## Test regime` is managed.** PAD's values hold; a repo's rows may add to them and tighten
  them, never remove or relax one, and `preflight.sh` fails the key it finds. `Tiers: none`
  keeps today's gates, and is what migration 0005 gives an installed repo.
- **Protected paths and the protected surface are two concepts.** Protected paths (existing)
  decide which tickets take the strict red discipline. The protected surface (new) is what
  only a suite ticket may change: `.claude/workflow/**`, `.claude/settings.json`, CI workflow
  files, `.pre-commit-config.yaml`, the suite map, the adapter's `protected-files`, and the
  repo's additions. `task-submit.sh` rejects `needs-suite-owner: <path>`, and so does
  `merge-task.sh --protected`.
- **Every rule carries a `warrant:`**, the failure that earned it; PAD's own come from
  decisions 0004 to 0006 and the KAN runs. A rule with none, or with a kind that has no
  enforcement point, fails `rules.sh validate`. The kinds are `test-removal`, `test-authoring`,
  `practice`, `tier-contract`, `suite-structure`, `acceptance` and `repo-lint`.
- **Harness lints are `repo-lint` rules**, shipped opt-in in `rules/optional/`
  (`scope-docs-updated`, `layout-as-declared`). Copied into `rules/`, `task-submit.sh` runs
  the check over the whole diff and it can fail the submit.
- **Acceptance tests are marked by the ticket key in the file name**, in the place the runner
  discovers tests, and are distinct from flaky quarantine: one awaits a verdict, the other is
  capped and still runs.

## Alternatives rejected
- Rejected: `taskkill /T` alone, or no sweep. It misses re-parented grandchildren, so
  processes outlive their runs.
- Rejected: PAD-only memory, or two cap numbers. The operator wants a guarantee about the
  machine, not an estimate about PAD.
- Rejected: several adapters per repo, or repo-written adapters only. Peers, not defaults, and
  PAD's own cover the common runners.
- Rejected: a `repo-lint` check as a plugin (it cannot fail a submit), or always on (it would
  bind repos that never asked for it).
- Rejected: one concept for the protected paths and the protected surface; the first picks a
  discipline for a ticket, the second reserves files for one owner.
- Rejected: a quarantine directory for acceptance tests; colocated stacks (vitest) break on it.
