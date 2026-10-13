# 0002 — PAD 0.3.0: rules, derived files, gate options and knowledge packages

Applies when: `.claude/workflow/config.md` records a `PAD version:` older than `0.3.0`.

## Steps

The files are already updated; these are the changes copying files cannot make.

1. **Two allow rules.** Agents now run `rules.sh` at start, and `merge-task.sh` runs
   `affected-tests.sh`. Name both in the pull request;
   the operator adds them to `.claude/settings.json`'s `permissions.allow`:
   - `Bash(bash .claude/workflow/bin/rules.sh *)`
   - `Bash(bash .claude/workflow/bin/affected-tests.sh *)`
2. **Config.** Run `/setup-workflow upgrade`. It records `PAD version: 0.3.0` and adds the rows
   0.3.0's `config.example.md` has and the config lacks, with their defaults: Commands
   `Dev tests` and `Derived files`, Execution `Gate` and `Test workers`. Fill Derived files
   only for a line every task changes (a count in a README, a lockfile).
3. **Repo rules.** A rule this project needs beyond PAD's goes in `.claude/workflow/rules/`
   as its own file (`.claude/workflow/bin/rules.sh` documents the format). Nothing to do if
   there is none.
4. **Packages.** In a repo of several packages, run `/knowledge-layer refresh`: it proposes the
   `Packages:` line for the config's `## Project knowledge` section and adopts any
   `<package>/PROJECT.md` and `<package>/CONTEXT.md` already there.

## Check

`bash .claude/workflow/bin/preflight.sh` prints `PREFLIGHT OK`: no `version`, `commands` or
`rules` failure.
