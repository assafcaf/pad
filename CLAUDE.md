# PAD

## This repo builds the workflow it runs on

`payload/` is the product: what `install.sh` copies into a project. `.claude/` is an installed
copy of that payload, used to build PAD with its own workflow. Change the workflow in
`payload/`, never in `.claude/`; refresh `.claude/` by re-running `install.sh` only after the
epic that changed the payload has merged, so a run never edits the harness it is running on.

## Delivering work

New work flows through `/spec` (idea → scope: references, protected paths, domains),
`/tickets` (scope → ownership units in the tracker, linted by `plan-check.sh`) and `/pad-run`
(tickets → one owner each, merged by `merge-task.sh`, tracker updated by the scripts). The
definition of done is `.claude/workflow/definition-of-done.md`; per-repo settings are in
`.claude/workflow/config.md`. Durable decisions go in `docs/decisions/`.

## Running the tests

- Fast (default, under a minute): `python -m pytest -q -n 8 tests` — the content tests and at
  least one quick test per payload script; tests marked `slow` are skipped (`addopts` in
  `pyproject.toml`).
- Full (before a merge or a release): `python -m pytest -q -n 8 -m "" tests`; only the slow
  tier: `-m slow`.
- `-n 8` needs pytest-xdist (`python -m pip install pytest-xdist`); drop it to run serially.
- Mark a new test `@pytest.mark.slow` when it runs a payload script for more than about a second.

Keep committed files machine-neutral: no absolute paths, no one OS's shell. Host-specific facts
go in your own gitignored `CLAUDE.local.md`.
