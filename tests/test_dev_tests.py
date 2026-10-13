"""Two test tiers: permanent outcome tests merge and stay; development tests are scaffolding that
never reaches the epic branch.

The dev-tests-stay-out rule (test-authoring) makes task-submit.sh, and so merge-task.sh, reject a
branch that adds a file under the dev path (config Commands row `Dev tests`, default
`tests/_dev/`) or a `pytest.mark.dev` test. The prose tells the code-writer where to put dev
tests and the ticket-owner to triage each one: promote or discard.
"""
from __future__ import annotations

from pathlib import Path

from conftest import git

WRITER = "claude/agents/code-writer.md"
OWNER = "claude/agents/ticket-owner.md"
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


def test_code_writer_keeps_dev_tests_uncommitted_and_reports_them(payload_text):
    text = payload_text(WRITER)
    assert "never commit a dev test" in text
    assert "DEV_TESTS:" in text


def test_owner_triages_every_dev_test_and_reports_it(payload_text):
    text = payload_text(OWNER)
    assert "**Triage the dev tests.**" in text
    assert "DEV_TESTS:" in text
    assert "<test> | promote | <outcome test it became>" in text


def test_config_names_the_dev_test_path(payload_text):
    assert "| Dev tests | `tests/_dev/`" in payload_text(CONFIG)
