---
name: merge-strategy
description: Turn a prose description of how this repo should merge READY tickets into a validated, rehearsed merge strategy (a <name>.md and <name>.sh pair) beside PAD's own. Run as /merge-strategy "<what it should do>". Refuses anything that breaks the merge contract. Do not start it unasked.
argument-hint: "<prose description of the merge behaviour>"
---

# Prose → merge strategy

Input: `$ARGUMENTS`. Read `.claude/workflow/config.md`, `docs/decisions/0006-merge-strategies.md`
and [STRATEGY-FORMAT.md](STRATEGY-FORMAT.md), which holds the file format, the script's
interface, the building blocks and a worked example. Run `bash .claude/workflow/bin/merge-strategies.sh list`
to see the strategies that exist (their names are taken, and `dynamic` is reserved).

A strategy decides three things, and nothing else: **grouping** (which READY tickets are tried
together), the **gate** (what is run on a group, and where), and **what to do on red** (which
tickets land, which are rejected, which go back to the queue). Every ticket still lands through
`merge-task.sh`; the engine checks this after each pass.

## 1. Map the description

Read the description and write down, for each of the three decisions, what it says:

| Decision | Examples of what the prose may say |
|---|---|
| Grouping | one at a time; all of them; groups of N (an option); by ticket order |
| Gate | the full gate; lint only; a command given as an option; run once per group or per ticket |
| On red | stop at the first failure; land the longest green prefix; reject the culprit and requeue the rest; fall back to one at a time |

Ask the operator only about what the description has left open, one question at a time, each with
a default you propose. Do not ask about anything it already says, and do not ask about the
file format, the names of the building blocks or the script's interface: those are fixed.
Pick the name from the description (lowercase letters, digits, hyphens) and confirm it only
when it clashes with the list.

## 2. Refuse what breaks the contract

Refuse each of these, saying why, and offer the nearest thing that keeps the contract:

- **Landing outside `merge-task.sh`** (a plain `git merge`, `git commit` or `git push` onto the
  epic branch, or editing the epic worktree). Why: `merge-task.sh` holds the submission
  checks, the protected-path and test-removal rules and the bookkeeping, and the engine fails
  any pass whose epic commits did not come from it. Offer: group and gate however you like,
  and land with `merge-task.sh --expect-tree`.
- **Skipping a submission check** (`task-submit.sh`, the ownership check, the protected-path
  rule, the test-removal rules, the red-commit proof). Why: they are the only evidence that
  the ticket's own tests were written and kept. Offer: a faster gate, never fewer checks.
- **Dropping the epic's final gate** (a strategy whose gate is a no-op, or that lets the run
  finish without the full gate on the epic branch). Why: a strategy may gate a group's final
  tree only, so the epic's final full gate is the backstop for the states between tickets.
  Offer: a lighter gate per group, with the full gate left to the end of the run.

A description that is only the refused thing gets no files. A description with a refusable part
gets files for the rest, and says which part it left out.

## 3. Write the pair

Write `.claude/workflow/merge-strategies/<name>.md` and `<name>.sh` in the format of
[STRATEGY-FORMAT.md](STRATEGY-FORMAT.md). The script calls only `merge-candidate.sh`,
`merge-gate.sh` and `merge-task.sh` from `$PAD_BIN`, plus plain shell. Mark it executable
(`git update-index --chmod=+x` on a host that does not keep the mode), keep LF line endings,
and never write into `.claude/workflow/bin/` or any strategy PAD ships. Each option the
description wants tunable is declared in `options:` with a default and read as
`PAD_OPT_<NAME>`.

**The "when to use" body** is what `dynamic` reads when it chooses among strategies, so write
it in terms of what the orchestrator sees, never in terms of the repo's code: the lines of
`merge.sh --status` (`QUEUE <n>`, `DRAIN running|idle`,
`LAST <strategy> merged=<n> rejected=<n> conflict=<n> gates=<n>`) and the result lines
(`MERGED`, `REJECTED`, `CONFLICT`, `ERROR`). For example: "Use when `QUEUE` holds two or more
and the last pass had `rejected=0`. Avoid after two passes in a row with `rejected` above 0."

## 4. Allow rules, with consent

List every command the script runs through the permission system, and the allow rule it needs
(`Bash(bash .claude/workflow/merge-strategies/<name>.sh *)`, and one for any other command the
script runs, such as the gate command an option names). Show the list. Add each rule to
`.claude/settings.json` (or `.claude/settings.local.json`) only with the operator's consent,
one rule at a time if they ask. Never edit a deny rule, never add a broader rule than the
command needs, and never add one without consent.

## 5. Validate, then rehearse

1. `bash .claude/workflow/bin/merge-strategies.sh validate` must print no `STRATEGY FAIL`. Fix
   the files and run it again until it is clean; it checks the frontmatter, the script, the
   name and the config's line.
2. `bash .claude/workflow/bin/merge-strategies.sh rehearse <name>` must print `REHEARSAL OK`.
   It drives a green batch, a conflict and a red ticket on a scratch repo with fixture gates.
   On `REHEARSAL FAILED`, read the broken check it names, fix the script, and run both steps
   again. Do not tell the operator the strategy works before both pass.

The rehearsal uses fixture gates, so it proves the control flow and not the real gate command.
Offer to run that command once at the epic head.

## 6. Offer the default

Say where the files are and how to use the strategy for one run
(`/pad-run --merge <name> [opt=val]`). Then offer to make it the repo's default by setting the
config's `Merge strategy: <name> [opt=val]` line. Change that line only when the operator
accepts; otherwise the config is left exactly as it was. Under the default `dynamic`, the new
strategy is already a candidate through its "when to use" text.

## Never

- Write a strategy that lands without `merge-task.sh`, skips a check, or drops the final gate.
- Name a strategy `dynamic`, or reuse a name on the list.
- Edit a strategy PAD ships, or any file outside `merge-strategies/`, the settings file (with
  consent) and the config line (when accepted).
- Commit anything: the operator reviews the files first.
