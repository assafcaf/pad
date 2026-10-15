"""Two test tiers: permanent outcome tests merge and stay; development tests are scaffolding that
never reaches the epic branch.

The dev-tests-stay-out rule (test-authoring) makes task-submit.sh, and so merge-task.sh, reject a
branch that adds a file under the dev path (config Commands row `Dev tests`, default
`tests/_dev/`) or a `pytest.mark.dev` test. The prose tells the owner where to put dev tests
and to triage each one before it submits: promote or delete.
"""
from __future__ import annotations

import re
from pathlib import Path

from conftest import git

OWNER = "claude/agents/owner.md"
TESTING = "claude/workflow/testing.md"
CONFIG = "claude/workflow/config.example.md"


def _commit(wt: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        p = wt / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        git("add", rel, cwd=wt)
    git("commit", "-q", "-m", msg, cwd=wt)
    return git("rev-parse", "HEAD", cwd=wt)


def _submit(run_script, repo, worktree, files: dict[str, str], config: str | None = None):
    if config is not None:
        _commit(repo, {".claude/workflow/config.md": config}, "config")
    epic = git("rev-parse", "HEAD", cwd=repo)
    wt = worktree(repo, "t-dev")
    git("reset", "-q", "--hard", epic, cwd=wt)
    red = _commit(wt, {"tests/test_x.py": "def test_x():\n    assert False\n"}, "test(T-1): o1 [red]")
    head = _commit(wt, files, "feat(T-1): impl")
    return run_script("task-submit.sh", epic, red, head, "--test-paths", "tests/", cwd=wt)


def _last(r) -> str:
    return r.stdout.strip().splitlines()[-1]


def test_a_committed_file_under_the_default_dev_path_is_rejected(run_script, repo, worktree):
    r = _submit(run_script, repo, worktree, {
        "src/x.py": "X = 1\n",
        "tests/_dev/test_step.py": "def test_step():\n    assert True\n",
    })
    assert r.returncode == 1
    assert _last(r).startswith("SUBMIT FAIL test-changed-after-red") or "dev-tests-stay-out" in _last(r)


def test_a_dev_file_in_the_red_commit_is_rejected_by_the_rule(run_script, repo, worktree):
    epic = git("rev-parse", "HEAD", cwd=repo)
    wt = worktree(repo, "t-dev-red")
    git("reset", "-q", "--hard", epic, cwd=wt)
    red = _commit(wt, {
        "tests/test_x.py": "def test_x():\n    assert False\n",
        "tests/_dev/test_step.py": "def test_step():\n    assert True\n",
    }, "test(T-1): o1 [red]")
    r = run_script("task-submit.sh", epic, red, red, "--test-paths", "tests/", cwd=wt)
    assert r.returncode == 1
    assert _last(r).startswith("SUBMIT FAIL test-authoring: dev-tests-stay-out")


def test_a_dev_marked_test_is_rejected(run_script, repo, worktree):
    epic = git("rev-parse", "HEAD", cwd=repo)
    wt = worktree(repo, "t-dev-mark")
    git("reset", "-q", "--hard", epic, cwd=wt)
    red = _commit(wt, {
        "tests/test_x.py": "import pytest\n\n\n@pytest.mark.dev\ndef test_x():\n    assert False\n",
    }, "test(T-1): o1 [red]")
    r = run_script("task-submit.sh", epic, red, red, "--test-paths", "tests/", cwd=wt)
    assert r.returncode == 1
    assert "dev-tests-stay-out" in _last(r)


def test_the_dev_path_comes_from_the_config(run_script, repo, worktree):
    config = "## Commands\n\n| Gate | Command |\n|---|---|\n| Dev tests | `tests/scratch/` |\n"
    _commit(repo, {".claude/workflow/config.md": config}, "config")
    epic = git("rev-parse", "HEAD", cwd=repo)
    wt = worktree(repo, "t-dev-cfg")
    git("reset", "-q", "--hard", epic, cwd=wt)
    red = _commit(wt, {
        "tests/test_x.py": "def test_x():\n    assert False\n",
        "tests/scratch/test_step.py": "def test_step():\n    assert True\n",
    }, "test(T-1): o1 [red]")
    r = run_script("task-submit.sh", epic, red, red, "--test-paths", "tests/", cwd=wt)
    assert "dev-tests-stay-out" in _last(r)


def test_permanent_tests_alone_pass(run_script, repo, worktree):
    epic = git("rev-parse", "HEAD", cwd=repo)
    wt = worktree(repo, "t-perm")
    git("reset", "-q", "--hard", epic, cwd=wt)
    red = _commit(wt, {"tests/test_x.py": "def test_x():\n    assert False\n"}, "test(T-1): o1 [red]")
    r = run_script("task-submit.sh", epic, red, red, "--test-paths", "tests/", cwd=wt)
    assert _last(r) == "SUBMIT OK", r.stdout


# --- prose --------------------------------------------------------------------------------------


def test_testing_guide_describes_both_tiers(payload_text):
    text = payload_text(TESTING)
    assert "## Permanent and development tests" in text
    assert "tests/_dev/" in text
    assert "promote" in text and "discard" in text


def _dev_step(text: str) -> str:
    paras = [p for p in re.split(r"\n(?=\s*(?:\d+\.|##)\s)", text) if "**Dev tests.**" in p]
    assert paras, "owner.md has no Dev tests step"
    return " ".join(paras[0].split())


def test_owner_writes_dev_tests_under_the_dev_path_and_never_commits_one(payload_text):
    step = _dev_step(payload_text(OWNER))
    assert "under the config's dev path" in step
    assert "Never commit one." in step


def test_owner_promotes_or_deletes_every_dev_test_before_it_submits(payload_text):
    step = _dev_step(payload_text(OWNER))
    assert "Before you submit, promote any that checks behaviour a caller relies on" in step
    assert "delete the rest" in step


def test_owner_under_strict_gets_a_promoted_dev_test_as_a_follow_up_red(payload_text):
    step = _dev_step(payload_text(OWNER))
    assert "strict: ask `<KEY>-tests` for a follow-up red commit" in step
    assert "the `rebase-red` move" in step


def test_config_names_the_dev_test_path(payload_text):
    assert "| Dev tests | `tests/_dev/`" in payload_text(CONFIG)
