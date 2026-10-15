"""The merge gate's cost: gate=affected, a worker budget, and no orphaned gate processes.

    merge-task.sh ... [--affected "<named tests cmd with {tests}>"] [--workers <n>] ...

--affected runs the named-tests command on affected-tests.sh's selection instead of the full
suite, and the full suite when it says FULL. --workers fills `{workers}` in the gate and affected
commands. A merge killed while its gate runs takes the gate's whole process tree with it.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from conftest import BASH, BIN, git

pytestmark = pytest.mark.slow

SCRIPT = "merge-task.sh"
KEY = "T-1"
GOAL = "Add the impl"


def _commit(wt: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        p = wt / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        git("add", rel, cwd=wt)
    git("commit", "-q", "-m", msg, cwd=wt)
    return git("rev-parse", "HEAD", cwd=wt)


def _setup(repo: Path, worktree):
    epic = worktree(repo, "epic")
    first = _commit(epic, {"src/base.py": "BASE = 1\n"}, "epic: base")
    git("push", "-q", "-u", "origin", "epic", cwd=epic)
    task = worktree(repo, "task")
    git("reset", "-q", "--hard", first, cwd=task)
    red = _commit(task, {"tests/test_new.py": "def test_new():\n    assert False\n"},
                  f"test({KEY}): O1 [red]")
    head = _commit(task, {"src/impl.py": "X = 1\n"}, f"feat({KEY}): impl")
    return epic, red, head


def _args(epic: Path, gate: str, *extra: str) -> list[str]:
    return ["--worktree", epic.as_posix(), "--branch", "epic", *extra,
            "--gate", gate, "--lint", "true", KEY]


def test_gate_affected_runs_only_the_selected_tests(repo, worktree, run_script, tmp_path):
    epic, red, head = _setup(repo, worktree)
    ran = tmp_path / "ran.txt"
    r = run_script(SCRIPT, *_args(epic, f'echo FULL > "{ran.as_posix()}"', "--affected",
                                  f'echo {{tests}} > "{ran.as_posix()}"'),
                   red, head, GOAL, cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert ran.read_text(encoding="utf-8").strip() == "tests/test_new.py"
    assert "gate: affected (tests/test_new.py)" in r.stdout


def test_gate_affected_falls_back_to_the_full_suite(repo, worktree, run_script, tmp_path):
    epic, red, _ = _setup(repo, worktree)
    task = repo.parent / "wt-task"
    head = _commit(task, {"pyproject.toml": "[project]\nname = 'x'\n"}, f"feat({KEY}): deps")
    ran = tmp_path / "ran.txt"
    r = run_script(SCRIPT, *_args(epic, f'echo FULL > "{ran.as_posix()}"', "--affected",
                                  f'echo {{tests}} > "{ran.as_posix()}"'),
                   red, head, GOAL, cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert ran.read_text(encoding="utf-8").strip() == "FULL"
    assert "gate: full (pyproject.toml changed)" in r.stdout


def test_workers_fills_the_gate_command(repo, worktree, run_script, tmp_path):
    epic, red, head = _setup(repo, worktree)
    seen = tmp_path / "w.txt"
    r = run_script(SCRIPT, *_args(epic, f'echo {{workers}} > "{seen.as_posix()}"', "--workers", "3"),
                   red, head, GOAL, cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert seen.read_text(encoding="utf-8").strip() == "3"


def test_a_killed_merge_takes_its_gate_process_tree_with_it(repo, worktree, tmp_path):
    epic, red, head = _setup(repo, worktree)
    pidfile = tmp_path / "child.pid"
    gate = f'sleep 300 & echo $! > "{pidfile.as_posix()}"; wait'
    driver = tmp_path / "driver.sh"
    driver.write_text(
        "set -u\n"
        f'bash "{(BIN / SCRIPT).as_posix()}" '
        + " ".join(f"'{a}'" for a in _args(epic, gate)) + f" {red} {head} '{GOAL}' &\n"
        "m=$!\n"
        f'for i in $(seq 1 200); do [ -s "{pidfile.as_posix()}" ] && break; sleep 0.1; done\n'
        "kill -TERM $m\n"
        "wait $m\n"
        f'c="$(cat "{pidfile.as_posix()}")"\n'
        "for i in $(seq 1 50); do kill -0 \"$c\" 2>/dev/null || { echo GONE; exit 0; }; sleep 0.1; done\n"
        'kill -KILL "$c" 2>/dev/null; echo ALIVE\n',
        encoding="utf-8",
    )
    started = time.monotonic()
    r = subprocess.run([BASH, driver.as_posix()], cwd=str(repo), capture_output=True, text=True,
                       timeout=120, check=False)
    assert r.stdout.strip().splitlines()[-1] == "GONE", (r.stdout, r.stderr)
    assert time.monotonic() - started < 60
    assert git("status", "--porcelain", cwd=epic) == ""
