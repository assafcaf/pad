"""O9, O10: merge-task.sh lands a ticket whose tree was already gated, and runs under a held lock.

O9: `--expect-tree <tree> [--batch-label "<text>"]` checks the merged tree against <tree> instead
of running the gate; the evidence records `<gate> -> pass (<label>, tree <short>)`. A different
tree is `REJECTED <KEY>: tree <have> != <want>` with the epic head unchanged. Submission,
ownership and protected-path checks reject as they do without the flag.

O10: with the merge lock `<git common dir>/pad-locks/merge` held by pid P, `PAD_MERGE_LOCK_HELD=P`
lets the merge proceed without waiting and leaves the lock in place; any other value waits.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from conftest import BASH, BIN, git, kill_tree

pytestmark = pytest.mark.slow

KEY = "E1-T1"
GOAL = "Add the impl"
GATE = 'grep -q "X = 1" src/impl.py'
RUN = "R1"
WRONG_TREE = "0" * 40


def _commit(wt: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        p = wt / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        git("add", rel, cwd=wt)
    git("commit", "-q", "-m", msg, cwd=wt)
    return git("rev-parse", "HEAD", cwd=wt)


def _epic(repo: Path, worktree) -> tuple[Path, str]:
    wt = worktree(repo, "epic")
    head = _commit(wt, {"src/base.py": "BASE = 1\n"}, "epic: base")
    git("push", "-q", "-u", "origin", "epic", cwd=wt)
    return wt, head


def _task(repo: Path, worktree, epic_head: str) -> tuple[Path, str, str]:
    wt = worktree(repo, "task")
    git("reset", "-q", "--hard", epic_head, cwd=wt)
    red = _commit(
        wt, {"tests/test_new.py": "def test_new():\n    assert False\n"}, f"test({KEY}): O1 [red]"
    )
    head = _commit(wt, {"src/impl.py": "X = 1\n"}, f"feat({KEY}): impl")
    return wt, red, head


def _args(epic_wt: Path, red: str, head: str, *, gate: str = GATE, extra: tuple[str, ...] = ()):
    return [
        BASH, (BIN / "merge-task.sh").as_posix(),
        "--worktree", epic_wt.as_posix(), "--branch", "epic", *extra,
        "--gate", gate, "--lint", "true", KEY, red, head, GOAL,
    ]


def _run(repo, epic_wt, red, head, *, gate=GATE, extra=()):
    return subprocess.run(
        _args(epic_wt, red, head, gate=gate, extra=extra), cwd=str(repo),
        capture_output=True, text=True, encoding="utf-8", check=False, timeout=120,
    )


def _last(r) -> str:
    lines = r.stdout.strip().splitlines()
    return lines[-1] if lines else ""


def _tree(wt: Path, rev: str) -> str:
    # The task is cut from the epic head, so the merged tree is the task head's tree.
    return git("rev-parse", f"{rev}^{{tree}}", cwd=wt)


def _origin_epic(repo: Path) -> str:
    return git("rev-parse", "refs/heads/epic", cwd=repo.parent / "origin.git")


def _untouched(epic_wt: Path, epic_head: str, r) -> None:
    out = r.stdout + r.stderr
    assert git("rev-parse", "HEAD", cwd=epic_wt) == epic_head, out
    assert git("status", "--porcelain", cwd=epic_wt) == "", out
    assert git("ls-files", "src/impl.py", cwd=epic_wt) == "", out


# O9 ---------------------------------------------------------------------------------------------


def test_matching_tree_is_merged_without_running_the_gate(repo, worktree, tmp_path):
    epic_wt, epic_head = _epic(repo, worktree)
    twt, red, head = _task(repo, worktree, epic_head)
    ran = tmp_path / "gate-ran"
    r = _run(repo, epic_wt, red, head, gate=f'touch "{ran.as_posix()}"',
             extra=("--expect-tree", _tree(twt, head)))
    assert r.returncode == 0, r.stdout + r.stderr
    new_head = git("rev-parse", "HEAD", cwd=epic_wt)
    assert _last(r) == f"MERGED {new_head}"
    assert git("log", "-1", "--format=%s", cwd=epic_wt) == f"Merge {KEY}: {GOAL}"
    assert git("log", "-1", "--format=%P", cwd=epic_wt).split() == [epic_head, head]
    assert _origin_epic(repo) == new_head
    assert list(tmp_path.glob("gate-ran")) == []


def test_matching_tree_with_run_records_the_gated_batch_and_tree_in_the_evidence(repo, worktree):
    ticket = repo / ".work" / "tickets" / "E1" / f"{KEY}.md"
    ticket.parent.mkdir(parents=True)
    ticket.write_bytes(f"---\nkey: {KEY}\nstatus: doing\n---\n\n## Outcome\nx\n".encode())
    epic_wt, epic_head = _epic(repo, worktree)
    twt, red, head = _task(repo, worktree, epic_head)
    tree = _tree(twt, head)
    r = _run(repo, epic_wt, red, head,
             extra=("--expect-tree", tree, "--batch-label", "B-7", "--run", RUN))
    assert r.returncode == 0, r.stdout + r.stderr
    sha = git("rev-parse", "HEAD", cwd=epic_wt)
    assert _last(r) == f"MERGED {sha}"
    assert "BOOKKEEPING FAIL" not in r.stdout
    evidence = (repo / ".work" / "runs" / RUN / f"{KEY}.md").read_text(encoding="utf-8")
    assert f"- Merge commit: {sha}" in evidence
    assert f"- Green gate: {GATE} -> pass (B-7, tree {tree[:7]}" in evidence
    assert "status: done" in ticket.read_text(encoding="utf-8")


def test_different_tree_is_rejected_naming_both_and_leaves_the_epic_head(repo, worktree):
    epic_wt, epic_head = _epic(repo, worktree)
    twt, red, head = _task(repo, worktree, epic_head)
    r = _run(repo, epic_wt, red, head, extra=("--expect-tree", WRONG_TREE))
    assert r.returncode == 1, r.stdout + r.stderr
    have = _tree(twt, head)
    assert _last(r) in (
        f"REJECTED {KEY}: tree {have} != {WRONG_TREE}",
        f"REJECTED {KEY}: tree {have[:7]} != {WRONG_TREE}",
    )
    _untouched(epic_wt, epic_head, r)
    assert _origin_epic(repo) == epic_head


def test_expect_tree_still_rejects_a_test_edited_after_red(repo, worktree):
    epic_wt, epic_head = _epic(repo, worktree)
    twt, red, _ = _task(repo, worktree, epic_head)
    head = _commit(twt, {"tests/test_new.py": "def test_new():\n    assert True\n"},
                   f"feat({KEY}): edit test")
    r = _run(repo, epic_wt, red, head, extra=("--expect-tree", _tree(twt, head)))
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r).startswith(f"REJECTED {KEY}:")
    assert "test-changed-after-red" in _last(r)
    _untouched(epic_wt, epic_head, r)


def test_expect_tree_still_rejects_a_change_outside_the_ticket_owns(repo, worktree, tmp_path):
    epic_wt, epic_head = _epic(repo, worktree)
    twt, red, head = _task(repo, worktree, epic_head)
    ticket = tmp_path / f"{KEY}.md"
    ticket.write_bytes(b"## Outcome\nx\n\n## Owns\n- src/other/\n\n## Touches\nnone\n")
    r = _run(repo, epic_wt, red, head,
             extra=("--expect-tree", _tree(twt, head), "--ticket", ticket.as_posix()))
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r).startswith(f"REJECTED {KEY}: ownership")
    _untouched(epic_wt, epic_head, r)


def test_expect_tree_still_rejects_a_protected_path_without_the_designer_trailer(repo, worktree):
    epic_wt, epic_head = _epic(repo, worktree)
    twt, red, head = _task(repo, worktree, epic_head)
    r = _run(repo, epic_wt, red, head,
             extra=("--expect-tree", _tree(twt, head), "--protected", "src/*"))
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r).startswith(f"REJECTED {KEY}: needs-strict")
    _untouched(epic_wt, epic_head, r)


# O10 --------------------------------------------------------------------------------------------


@pytest.fixture
def holder():
    """A live process whose shell pid (the one `kill -0` sees in bash) owns the merge lock."""
    p = subprocess.Popen([BASH, "-c", "echo $$; exec sleep 600"], stdout=subprocess.PIPE, text=True)
    pid = p.stdout.readline().strip()
    yield pid
    if pid.isdigit():
        kill_tree(int(pid))  # Git's bash.exe is a launcher: Popen.kill() alone leaves the sleep
    p.kill()
    p.wait(timeout=30)
    p.stdout.close()


def _take_lock(repo: Path, pid: str) -> Path:
    common = (repo / git("rev-parse", "--git-common-dir", cwd=repo)).resolve()
    lock = common / "pad-locks" / "merge"
    lock.mkdir(parents=True)
    (lock / "pid").write_text(pid + "\n", encoding="utf-8")
    return lock


def _start(repo, epic_wt, red, head, *, gate=GATE, env=None):
    # Output goes to a file, not a pipe: a leaked pipe handle would block reading it.
    out = repo.parent / "merge.out"
    with out.open("wb") as f:
        proc = subprocess.Popen(
            _args(epic_wt, red, head, gate=gate), cwd=str(repo),
            env={**os.environ, **(env or {})}, stdout=f, stderr=subprocess.STDOUT,
        )
    proc.out = out
    return proc


def _finish(proc, timeout: float) -> str | None:
    """The merge's output once it exits within <timeout>, else None (and it is killed)."""
    deadline = time.monotonic() + timeout
    while proc.poll() is None and time.monotonic() < deadline:
        time.sleep(0.1)
    killed = proc.poll() is None
    if killed:
        proc.kill()
        proc.wait(timeout=30)
    return None if killed else proc.out.read_text(encoding="utf-8")


def test_merge_under_the_lock_named_in_pad_merge_lock_held_proceeds_and_leaves_the_lock(
    repo, worktree, holder
):
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, head = _task(repo, worktree, epic_head)
    lock = _take_lock(repo, holder)
    proc = _start(repo, epic_wt, red, head, env={"PAD_MERGE_LOCK_HELD": holder})
    out = _finish(proc, 40)
    assert out is not None, "merge waited for a lock its caller holds"
    new_head = git("rev-parse", "HEAD", cwd=epic_wt)
    assert out.strip().splitlines()[-1] == f"MERGED {new_head}", out
    assert (lock / "pid").read_text(encoding="utf-8").strip() == holder


@pytest.mark.parametrize("env", [{"PAD_MERGE_LOCK_HELD": "999999"}, {}], ids=["other-value", "unset"])
def test_merge_waits_for_a_held_lock_unless_its_pid_is_named(repo, worktree, holder, tmp_path, env):
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, head = _task(repo, worktree, epic_head)
    lock = _take_lock(repo, holder)
    ran = tmp_path / "gate-ran"
    proc = _start(repo, epic_wt, red, head, gate=f'touch "{ran.as_posix()}"; {GATE}',
                  env={"PAD_MERGE_LOCK_HELD": "", **env})
    try:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and proc.poll() is None:
            time.sleep(0.1)
        assert proc.poll() is None and list(tmp_path.glob("gate-ran")) == [], "merge did not wait for the held lock"
        shutil.rmtree(lock)
        out = _finish(proc, 60)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=30)
    assert out is not None, "merge never took the lock once it was released"
    assert out.strip().splitlines()[-1].startswith("MERGED "), out
