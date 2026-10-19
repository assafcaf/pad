# 0004 — Merge strategies: choose how tickets land

Applies when: `.claude/workflow/config.md` has no `Merge strategy:` line under `## Execution`.

## Steps

The files are already updated: `.claude/workflow/merge-strategies/` holds `single` and `batch`,
the `/merge-strategy` skill is installed, and any strategy of the project's own in that folder
was left alone. These are the changes copying files cannot make.

1. **Choose a strategy.** Ask the operator which to use: `dynamic` (the default: `/pad-run`
   picks among the strategies and switches as the run's signals change), `batch` (gate several
   tickets once and land the green prefix) or `single` (one ticket per gate, as before). Add
   a `Merge strategy:` line, `- **Merge strategy:** `<choice>``, under `## Execution` in
   `.claude/workflow/config.md`, with a sentence saying a fixed name uses only that strategy.
2. **Host suite slots.** Add `- **Host suite slots:** `none`` under `## Execution`; a number
   caps full-suite runs across every repo on this host (`bin/suite-slot.sh`).
3. **Gate.** Tell the operator the default `Gate:` is now `affected`, safe because the epic's
   final full gate runs the whole suite. Change the line only if they choose to; an existing
   value stays.
4. **Allow rules.** Name in the pull request the rules `.claude/settings.json` lacks from
   `settings.example.json`: one `Bash(bash .claude/workflow/bin/<script>.sh *)` for `merge`,
   `merge-strategies`, `merge-candidate`, `merge-gate`, `merge-ticket`, `merge-rehearse`,
   `merge-cancel` and `suite-slot`.

## Check

`bash .claude/workflow/bin/merge-strategies.sh validate` prints no failure.
