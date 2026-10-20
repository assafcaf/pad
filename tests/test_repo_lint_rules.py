"""E3-T4 O39: a `repo-lint` rule in rules/ runs over the whole diff at `task-submit.sh` and can
fail the submit; the same rule in rules/optional/ does nothing.

The rule's check gets `<epic head> <task head>` and reads the diff itself (no added-lines file:
a repo-lint rule is about the repo, not only its tests). A failure is
`SUBMIT FAIL repo-lint: <rule>: <first output lines>`. PAD_RULES_DIR points the scripts at a
fixture rules folder.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from conftest import git
from test_task_submit import _branch, _commit, _epic, _last, _red

LINT_RULE = """---
name: no-forbidden
kind: repo-lint
applies-to: orchestrator
check: no-forbidden.sh
warrant: a fixture rule, for the tests
---

No FORBIDDEN word anywhere in the diff.
"""

LINT_CHECK = """#!/usr/bin/env bash
if git diff "$1" "$2" | grep -q '^+.*FORBIDDEN'; then
  echo "found the FORBIDDEN word"
  exit 1
fi
exit 0
"""


def _rules_dir(tmp_path: Path, *, optional: bool) -> Path:
    d = tmp_path / "rules"
    target = d / "optional" if optional else d
    target.mkdir(parents=True)
    (target / "no-forbidden.md").write_text(LINT_RULE, encoding="utf-8")
    (target / "no-forbidden.sh").write_text(LINT_CHECK, encoding="utf-8")
    return d


def _branch_with(repo, worktree, impl: str):
    epic = _epic(repo)
    wt = _branch(repo, worktree, "t-lint", epic)
    red = _red(wt)
    head = _commit(wt, {"src/impl.py": impl}, "feat(T-1): impl")
    return wt, epic, red, head


def _submit(run_script, wt, epic, red, head, rules: Path):
    return run_script("task-submit.sh", epic, red, head, "--test-paths", "tests", cwd=wt,
                      env={"PAD_RULES_DIR": str(rules)})


@pytest.mark.slow
def test_o39_a_repo_lint_rule_in_rules_fails_the_submit_when_its_check_fails(
    repo, worktree, run_script, tmp_path
):
    wt, epic, red, head = _branch_with(repo, worktree, "X = 'FORBIDDEN'\n")
    r = _submit(run_script, wt, epic, red, head, _rules_dir(tmp_path, optional=False))
    assert r.returncode == 1, r.stdout + r.stderr
    last = _last(r)
    assert last.startswith("SUBMIT FAIL repo-lint:"), last
    assert "no-forbidden" in last and "FORBIDDEN word" in last


@pytest.mark.slow
def test_o39_the_same_failing_rule_in_optional_does_nothing(repo, worktree, run_script, tmp_path):
    wt, epic, red, head = _branch_with(repo, worktree, "X = 'FORBIDDEN'\n")
    live = _rules_dir(tmp_path, optional=False)
    assert _submit(run_script, wt, epic, red, head, live).returncode == 1
    inert = _rules_dir(tmp_path / "inert", optional=True)
    r = _submit(run_script, wt, epic, red, head, inert)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == "SUBMIT OK"


@pytest.mark.slow
def test_o39_the_check_sees_a_change_outside_the_test_paths_and_before_the_red_commit(
    repo, worktree, run_script, tmp_path
):
    """Whole diff: the epic head to the task head, not just the lines under the test paths."""
    rules = _rules_dir(tmp_path, optional=False)
    epic = _epic(repo)
    wt = _branch(repo, worktree, "t-lint2", epic)
    red = _commit(wt, {"docs/note.md": "FORBIDDEN\n", "tests/test_new.py":
                       "def test_new():\n    assert False\n"}, "test(T-1): o1 [red]")
    head = _commit(wt, {"src/impl.py": "X = 1\n"}, "feat(T-1): impl")
    r = run_script("task-submit.sh", epic, red, head, "--test-paths", "tests", cwd=wt,
                   env={"PAD_RULES_DIR": str(rules)})
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r).startswith("SUBMIT FAIL repo-lint:")


@pytest.mark.slow
def test_o39_the_shipped_rules_run_clean_on_an_empty_diff(repo, run_script):
    """PAD's optional repo-lint checks take `<epic> <head>` and pass when nothing changed."""
    from conftest import BASH, PAYLOAD
    import subprocess

    optional = PAYLOAD / "claude" / "workflow" / "rules" / "optional"
    head = git("rev-parse", "HEAD", cwd=repo)
    for name in ("scope-docs-updated", "layout-as-declared"):
        check = optional / f"{name}.sh"
        assert check.is_file(), f"{check} missing"
        r = subprocess.run([BASH, check.as_posix(), head, head], cwd=str(repo),
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, (name, r.stdout, r.stderr)
