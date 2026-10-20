# 0005 — Test regime: a `## Test regime` section, with cost tiers off

Applies when: `.claude/workflow/config.md` has no `## Test regime` section.

## Steps

The files are already updated: `bin/pad-test.sh`, the runner adapters (`runners/`), `host-setup.sh`,
`submit-surface.sh`, the `warrant:` on every shipped rule and the optional `repo-lint` rules in
`rules/optional/`. These are the changes copying files cannot make.

1. **Add the section.** Copy `## Test regime` from `.claude/workflow/config.example.md` to
   `.claude/workflow/config.md`, with Tiers: none (the line `- **Tiers:** none`). Every
   existing gate behaves as before, unchanged: no tier is enforced, and nothing runs through
   `pad-test.sh` until the operator runs `/setup-workflow` step 7g.
2. **The protected surface.** Tell the operator that a diff touching it now needs a suite
   ticket (`task-submit.sh` rejects `needs-suite-owner: <path>`): `.claude/workflow/**`,
   `.claude/settings.json`, CI workflow files, `.pre-commit-config.yaml`, the suite map
   (`tests/MAP.md` unless the config names another) and the runner adapter's protected files.
   A repo's own additions go on the `Protected surface:` line of the section.
3. **Rule warrants.** A rule the repo added to `.claude/workflow/rules/` now needs a
   `warrant:` line in its frontmatter (one line: the failure that earned the rule), or
   `rules.sh validate` fails. Add one to each, asking the operator when it is not clear.
4. **Allow and deny rules.** Do not write `.claude/settings.json`. Name in the pull request
   the rules it lacks from `settings.example.json`: `Bash(bash .claude/workflow/bin/pad-test.sh*)`
   in `permissions.allow`; the deny rules for the runner's own command come with
   `/setup-workflow` step 7g.

## Check

`bash .claude/workflow/bin/preflight.sh` prints no `regime` or `rules` failure.
