"""task-submit.sh --ticket: every changed path lies in the ticket's Owns or Touches."""
from __future__ import annotations

from pathlib import Path

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


def test_changes_inside_owns_and_touches_pass(repo, worktree, run_script, tmp_path):
    epic, wt, red = _setup(repo, worktree, "own-ok")
    head = _commit(wt, {"src/feature/a.py": "X = 1\n", "src/registry.py": "A = 1\nC = 2\n"}, "feat")
    t = _ticket(tmp_path, ["src/feature/"], ["src/registry.py"])
    r = _submit(run_script, wt, epic, red, head, t)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == "SUBMIT OK"


def test_path_outside_owns_fails(repo, worktree, run_script, tmp_path):
    epic, wt, red = _setup(repo, worktree, "own-out")
    head = _commit(wt, {"src/feature/a.py": "X = 1\n", "src/other.py": "B = 2\n"}, "feat")
    t = _ticket(tmp_path, ["src/feature"], [])
    r = _submit(run_script, wt, epic, red, head, t)
    assert r.returncode == 1
    assert _last(r) == "SUBMIT FAIL ownership: src/other.py"


def test_dir_prefix_is_not_a_dir_match(repo, worktree, run_script, tmp_path):
    epic, wt, red = _setup(repo, worktree, "own-prefix")
    head = _commit(wt, {"src/featurex/a.py": "X = 1\n"}, "feat")
    t = _ticket(tmp_path, ["src/feature"], [])
    r = _submit(run_script, wt, epic, red, head, t)
    assert _last(r) == "SUBMIT FAIL ownership: src/featurex/a.py"


def test_touches_losing_a_line_fails(repo, worktree, run_script, tmp_path):
    epic, wt, red = _setup(repo, worktree, "own-touch")
    head = _commit(wt, {"src/registry.py": "C = 2\n"}, "feat")
    t = _ticket(tmp_path, ["src/feature"], ["src/registry.py"])
    r = _submit(run_script, wt, epic, red, head, t)
    assert r.returncode == 1
    assert _last(r) == "SUBMIT FAIL ownership: src/registry.py (Touches is append-only)"


def test_owned_file_may_be_rewritten_or_deleted(repo, worktree, run_script, tmp_path):
    epic, wt, red = _setup(repo, worktree, "own-rewrite")
    head = _commit(wt, {"src/registry.py": None, "src/other.py": "rewritten\n"}, "feat")
    t = _ticket(tmp_path, ["src/registry.py", "src/other.py"], [])
    r = _submit(run_script, wt, epic, red, head, t)
    assert r.returncode == 0, r.stdout


def test_red_commit_tests_count_as_owned(repo, worktree, run_script, tmp_path):
    epic, wt, red = _setup(repo, worktree, "own-red")
    head = _commit(wt, {"src/feature/a.py": "X = 1\n"}, "feat")
    t = _ticket(tmp_path, ["src/feature"], [])
    r = _submit(run_script, wt, epic, red, head, t)
    assert r.returncode == 0, r.stdout


def test_existing_rules_still_report_first(repo, worktree, run_script, tmp_path):
    epic, wt, red = _setup(repo, worktree, "own-order")
    head = _commit(wt, {"tests/test_new.py": "def test_new():\n    assert True\n", "zzz.py": "1\n"}, "feat")
    t = _ticket(tmp_path, ["src"], [])
    r = _submit(run_script, wt, epic, red, head, t)
    assert _last(r).startswith("SUBMIT FAIL test-changed-after-red:")


def test_without_ticket_no_ownership_check(repo, worktree, run_script):
    epic, wt, red = _setup(repo, worktree, "own-none")
    head = _commit(wt, {"anywhere/x.py": "1\n"}, "feat")
    r = _submit(run_script, wt, epic, red, head)
    assert _last(r) == "SUBMIT OK"


def test_missing_ticket_file_is_usage(repo, worktree, run_script, tmp_path):
    epic, wt, red = _setup(repo, worktree, "own-usage")
    r = _submit(run_script, wt, epic, red, red, (tmp_path / "nope.md").as_posix())
    assert r.returncode == 64
