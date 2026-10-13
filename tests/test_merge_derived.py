"""Derived files: a line every task changes (a count, a lockfile) is rebuilt at merge, not rebased.

    merge-task.sh ... --derived "<path>=<cmd>" [--derived ...] <KEY> <RED> <TASK_HEAD> "<GOAL>"

When a merge conflicts only in derived files, merge-task.sh takes the epic's copy of each, runs
its command in the epic worktree on the merged tree, stages the result and gates as usual. Any
other conflicted path, or a command that fails, is still CONFLICT with the epic untouched.
"""
from __future__ import annotations

from pathlib import Path

from conftest import git

SCRIPT = "merge-task.sh"
KEY = "T-1"
GOAL = "Add the impl"
PASS_GATE = 'grep -q "X = 1" src/impl.py'
COUNT = "COUNT.md"
REBUILD = f"{COUNT}=printf 'modules: %s\\n' \"$(ls src | wc -l | tr -d ' ')\" > {COUNT}"


def _commit(wt: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        p = wt / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        git("add", rel, cwd=wt)
    git("commit", "-q", "-m", msg, cwd=wt)
    return git("rev-parse", "HEAD", cwd=wt)


def _setup(repo: Path, worktree, task_extra: dict[str, str] | None = None,
           epic_extra: dict[str, str] | None = None):
    """Epic with src/base.py and COUNT.md; a task and a later epic commit both bump COUNT.md."""
    epic = worktree(repo, "epic")
    first = _commit(epic, {"src/base.py": "BASE = 1\n", COUNT: "modules: 1\n"}, "epic: base")
    git("push", "-q", "-u", "origin", "epic", cwd=epic)
    task = worktree(repo, "task")
    git("reset", "-q", "--hard", first, cwd=task)
    red = _commit(task, {"tests/test_new.py": "def test_new():\n    assert False\n"},
                  f"test({KEY}): O1 [red]")
    head = _commit(task, {"src/impl.py": "X = 1\n", COUNT: "modules: 2 (task)\n",
                          **(task_extra or {})},
                   f"feat({KEY}): impl")
    epic_head = _commit(epic, {"src/other.py": "Y = 1\n", COUNT: "modules: 2\n",
                               **(epic_extra or {})}, "Merge T-0: other task")
    git("push", "-q", "origin", "epic", cwd=epic)
    return epic, epic_head, red, head


def _merge(run_script, repo, epic, red, head, *derived: str):
    extra = []
    for d in derived:
        extra += ["--derived", d]
    return run_script(SCRIPT, "--worktree", epic.as_posix(), "--branch", "epic", *extra,
                      "--gate", PASS_GATE, "--lint", "true", KEY, red, head, GOAL, cwd=repo)


def _last(r) -> str:
    lines = r.stdout.strip().splitlines()
    return lines[-1] if lines else ""


def _untouched(epic: Path, epic_head: str, r) -> None:
    out = r.stdout + r.stderr
    assert git("rev-parse", "HEAD", cwd=epic) == epic_head, out
    assert git("status", "--porcelain", cwd=epic) == "", out


def test_without_derived_files_the_count_line_conflicts(repo, worktree, run_script):
    epic, epic_head, red, head = _setup(repo, worktree)
    r = _merge(run_script, repo, epic, red, head)
    assert _last(r) == f"CONFLICT {KEY}: {COUNT}"
    _untouched(epic, epic_head, r)


def test_a_derived_only_conflict_is_rebuilt_and_merged(repo, worktree, run_script):
    epic, _, red, head = _setup(repo, worktree)
    r = _merge(run_script, repo, epic, red, head, REBUILD)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r).startswith("MERGED ")
    assert git("show", f"HEAD:{COUNT}", cwd=epic) == "modules: 3"
    assert git("status", "--porcelain", cwd=epic) == ""


def test_a_conflict_outside_the_derived_files_is_still_conflict(repo, worktree, run_script):
    epic, epic_head, red, head = _setup(repo, worktree, task_extra={"src/base.py": "BASE = 't'\n"},
                                        epic_extra={"src/base.py": "BASE = 'e'\n"})
    r = _merge(run_script, repo, epic, red, head, REBUILD)
    assert r.returncode == 1
    assert _last(r).startswith(f"CONFLICT {KEY}:")
    assert "src/base.py" in _last(r)
    _untouched(epic, epic_head, r)


def test_a_failing_rebuild_is_conflict_and_leaves_the_epic_untouched(repo, worktree, run_script):
    epic, epic_head, red, head = _setup(repo, worktree)
    r = _merge(run_script, repo, epic, red, head, f"{COUNT}=exit 7")
    assert r.returncode == 1
    assert _last(r) == f"CONFLICT {KEY}: {COUNT} (rebuild failed: exit 7)"
    _untouched(epic, epic_head, r)


def test_a_merge_turns_on_rerere_for_the_epic_repo(repo, worktree, run_script):
    epic, _, red, head = _setup(repo, worktree)
    _merge(run_script, repo, epic, red, head, REBUILD)
    assert git("config", "--get", "rerere.enabled", cwd=epic) == "true"
