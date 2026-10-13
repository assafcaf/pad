# 0004. Test removals and test-writing practice are rules, not a gate nothing may pass

Date: 2026-10-13 · Status: accepted · Tracker: none · Supersedes: the "never override the
weakened-tests gate" rule from PAD #13

## Context
PAD #13 told the orchestrator and every owner that no ruling lets a merge accept a test that
`weakened-tests.sh` flags: keep the old title, give it a body asserting the new truth. The
reason was a permission classifier, which reads an override as a CI bypass and then denies
every later step of that merge.

In a project's epic (KAN-107, 2026-10-13) one task deleted a package and its nine test files
(about 140 tests) under an operator ruling written into its ticket. Keeping 140 titles with
rewritten bodies made no sense, and PAD had no other path: `weakened-tests.sh` had no
exemption and `merge-task.sh` no flag. The classifier rightly blocked the orchestrator from
switching the check off through `TEST_DEF`, and the operator ran the merge by hand, twice.
The same epic produced six more lessons about how tests are written (fixed sleeps,
platform skips, `Path.exists()` for removed code, pinned counts, full-suite runs in agents,
shared lists), each of which lived only in one run's notes.

## Decision
A rule is one Markdown file in `.claude/workflow/rules/` with frontmatter (`name`, `kind`,
`applies-to`, optional `check`, optional `claim`) and a body of guidance. PAD ships its rules
there; a repo adds its own beside them, and `/pad-update` never touches a file PAD did not ship.

- **Distribution.** Every agent that runs `Bash`, and the orchestrator, starts by running
  `rules.sh for <agent>` and follows what it prints. A new rule file is live for the agents it
  names with no edit anywhere else.
- **Enforcement by kind, wired once.** `test-removal` checks run inside `weakened-tests.sh`: a
  removed test passes only when a rule explains it (same name re-added, the code it tested
  deleted in the same diff, a `ported-from` marker). `test-authoring` checks run inside
  `task-submit.sh` over added test lines. `practice` rules are guidance only. Nothing switches
  the check off, so nothing an agent does reads as a bypass.
- **Neutral review.** The owner lists each deleted test in its `READY` block's `REMOVALS`,
  with the rule and a reason. The orchestrator runs `weakened-tests.sh --claims` itself; an
  unexplained removal or a claim naming the wrong rule is a question for the operator. The PR
  body lists every removal and its rule.
- **Validation.** `rules.sh validate`, run by PAD's tests and by `preflight.sh`, fails a rule
  with a missing field, a kind with no enforcement point, an `applies-to` naming an agent that
  does not load rules, or a check script that does not exist.

## Alternatives rejected
- A ruling-backed `merge-task.sh --allow-removed <list>`: it fixes deletions only, leaves the
  test-writing lessons in run notes, and still asks an agent to pass a flag whose purpose is to
  let a removal through.
- Keeping "never override" and rewriting deleted tests' bodies: unworkable for a deleted
  package, and the rewritten tests assert nothing anyone relies on.
- Exempting by environment variable (`TEST_DEF`, `WEAK_ADDED`): exactly what the classifier
  blocks, and invisible in the PR.

## Consequences
- A deletion no PAD rule explains needs a repo rule, written by the operator, before it lands.
  The rule's author owns its `applies-to` list.
- The rules that decide a merge are the ones installed beside the `merge-task.sh` the
  orchestrator runs, never the task branch's. A task that adds a rule cannot use it to explain
  its own removals; the rule lands first, on its own.
- The `code-deleted` check reads Python imports. Another stack gets its own repo rule.
- `tracker` (no `Bash`) and `gate-runner` (runs one named script) do not load rules; a rule
  naming either fails validation.
