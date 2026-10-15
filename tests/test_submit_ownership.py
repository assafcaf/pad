"""task-submit.sh --ticket: every changed path lies in the ticket's Owns or Touches."""
from __future__ import annotations

from pathlib import Path

import pytest

from conftest import git


def _commit(wt: Path, files: dict[str, str | None], msg: str) -> str:
    for rel, text in files.items():
        p = wt / rel
        if text is None:
            git("rm", "-q", rel, cwd=wt)
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        git("add", rel, cwd=wt)
    git("commit", "-q", "-m", msg, cwd=wt)
    return git("rev-parse", "HEAD", cwd=wt)


def _epic(repo: Path) -> str:
    return _commit(
        repo,
        {"src/registry.py": "A = 1\n", "src/other.py": "B = 1\n", "tests/test_old.py": "def test_old():\n    assert True\n"},
        "epic",
    )


def _ticket(tmp: Path, owns: list[str], touches: list[str]) -> str:
    p = tmp / "ticket.md"
    p.write_text(
        "## Outcome\nx\n\n## Owns\n"
        + "".join(f"- {o}\n" for o in owns)
        + "\n## Touches\n"
        + "".join(f"- {t}   (append-only)\n" for t in touches)
        + "\n## Protected\nno\n\n## Depends on\nnone\n",
        encoding="utf-8",
    )
    return p.as_posix()


def _setup(repo, worktree, name):
    epic = _epic(repo)
    wt = worktree(repo, name)
    git("reset", "-q", "--hard", epic, cwd=wt)
    red = _commit(wt, {"tests/test_new.py": "def test_new():\n    assert False\n"}, "test(T): o1 [red]")
    return epic, wt, red


def _submit(run_script, wt, epic, red, head, ticket=None):
    args = [epic, red, head, "--test-paths", "tests"]
    if ticket:
        args += ["--ticket", ticket]
    return run_script("task-submit.sh", *args, cwd=wt)


def _last(r) -> str:
    return r.stdout.strip().splitlines()[-1]


NO_TICKET = None
CASES = {
    # id: (changed files, Owns, Touches, exit code or None, last line or its prefix)
    "changes-inside-owns-and-touches-pass": (
        {"src/feature/a.py": "X = 1\n", "src/registry.py": "A = 1\nC = 2\n"},
        ["src/feature/"], ["src/registry.py"], 0, "SUBMIT OK"),
    "path-outside-owns-fails": (
        {"src/feature/a.py": "X = 1\n", "src/other.py": "B = 2\n"},
        ["src/feature"], [], 1, "SUBMIT FAIL ownership: src/other.py"),
    "dir-prefix-is-not-a-dir-match": (
        {"src/featurex/a.py": "X = 1\n"},
        ["src/feature"], [], None, "SUBMIT FAIL ownership: src/featurex/a.py"),
    "touches-losing-a-line-fails": (
        {"src/registry.py": "C = 2\n"},
        ["src/feature"], ["src/registry.py"], 1,
        "SUBMIT FAIL ownership: src/registry.py (Touches is append-only)"),
    "owned-file-may-be-rewritten-or-deleted": (
        {"src/registry.py": None, "src/other.py": "rewritten\n"},
        ["src/registry.py", "src/other.py"], [], 0, None),
    "red-commit-tests-count-as-owned": (
        {"src/feature/a.py": "X = 1\n"}, ["src/feature"], [], 0, None),
    "existing-rules-still-report-first": (
        {"tests/test_new.py": "def test_new():\n    assert True\n", "zzz.py": "1\n"},
        ["src"], [], None, "SUBMIT FAIL test-changed-after-red:"),
    "without-ticket-no-ownership-check": (
        {"anywhere/x.py": "1\n"}, NO_TICKET, [], None, "SUBMIT OK"),
}


@pytest.mark.slow
@pytest.mark.parametrize("files, owns, touches, code, last", list(CASES.values()), ids=list(CASES))
def test_ownership(repo, worktree, run_script, tmp_path, files, owns, touches, code, last):
    epic, wt, red = _setup(repo, worktree, "own")
    head = _commit(wt, files, "feat")
    t = None if owns is NO_TICKET else _ticket(tmp_path, owns, touches)
    r = _submit(run_script, wt, epic, red, head, t)
    if code is not None:
        assert r.returncode == code, r.stdout + r.stderr
    if last is not None:
        assert _last(r).startswith(last), r.stdout
        if not last.endswith(":"):
            assert _last(r) == last, r.stdout


def test_missing_ticket_file_is_usage(repo, worktree, run_script, tmp_path):
    epic, wt, red = _setup(repo, worktree, "own-usage")
    r = _submit(run_script, wt, epic, red, red, (tmp_path / "nope.md").as_posix())
    assert r.returncode == 64
