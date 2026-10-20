"""E2-T13 O5: `merge.sh --run <id> --cancel` stops a running drain cleanly.

A real drain (merge.sh --ready) runs a strategy fixture that behaves like a pass stuck in its
gate: it adds a detached `pad-candidate` worktree, leaves a merge in progress in the epic
worktree, starts a long-running child and then waits. Cancelling must leave no process of the
drain, no merge lock, no candidate worktree, and the epic worktree clean at its previous head.
"""
from __future__ import annotations

import os
import subprocess
import time

import pytest

from conftest import BASH, BIN, git, kill_naming, kill_tree

pytestmark = pytest.mark.slow

RUN = "R1"

STRATEGY = """#!/usr/bin/env bash
D="{d}"
cat > /dev/null
git -C "$PAD_EPIC_WORKTREE" worktree add -q --detach "$D/pad-candidate-1" HEAD
git -C "$PAD_EPIC_WORKTREE" merge -q --no-ff --no-commit task >/dev/null 2>&1
( echo $BASHPID > "$D/child.pid"; exec sleep 600 ) &
: > "$D/held"
wait
"""


def _alive(pid: str) -> bool:
    return subprocess.run([BASH, "-c", f"kill -0 {pid}"], capture_output=True).returncode == 0


def _wait(cond, secs: float = 90) -> bool:
    deadline = time.time() + secs
    while time.time() < deadline:
        if cond():
            return True
        time.sleep(0.1)
    return cond()


@pytest.fixture
def drain(repo, tmp_path, run_script):
    sdir = tmp_path / "strategies"
    sdir.mkdir()
    run_dir = repo / ".work" / "runs" / RUN
    run_dir.mkdir(parents=True)
    cfg = repo / ".claude" / "workflow" / "config.md"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("# Workflow config\n\n## Execution\n\nMerge strategy: hang\n", encoding="utf-8")
    exclude = repo / ".git" / "info" / "exclude"
    exclude.parent.mkdir(exist_ok=True)
    exclude.write_text(".claude/\n.work/\n", encoding="utf-8")
    (sdir / "hang.md").write_text(
        "---\nname: hang\nscript: hang.sh\ndescription: Hangs in its gate.\noptions: max=4\n---\n\n"
        "When to use: never.\n", encoding="utf-8")
    (sdir / "hang.sh").write_text(STRATEGY.format(d=sdir.as_posix()), encoding="utf-8", newline="\n")
    epic = repo / ".claude" / "worktrees" / RUN
    epic.parent.mkdir(parents=True)
    git("worktree", "add", "-q", "-b", "epic", epic.as_posix(), "main", cwd=repo)
    tw = tmp_path / "taskwt"
    git("worktree", "add", "-q", "-b", "task", tw.as_posix(), "main", cwd=repo)
    (tw / "task.txt").write_text("task\n", encoding="utf-8")
    git("add", "task.txt", cwd=tw)
    git("commit", "-q", "-m", "task change", cwd=tw)
    head = git("rev-parse", "epic", cwd=epic)
    thead = git("rev-parse", "task", cwd=repo)
    env = dict(os.environ, PAD_STRATEGIES_DIR=sdir.as_posix())
    proc = subprocess.Popen(
        [BASH, (BIN / "merge.sh").as_posix(), "--run", RUN, "--ready", "E1-T1", thead, head],
        cwd=str(repo), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert _wait(lambda: (sdir / "held").exists() or proc.poll() is not None), "drain never held"
        assert (sdir / "held").exists(), "drain ended early"
        assert _wait(lambda: (sdir / "child.pid").exists())
        yield {"repo": repo, "epic": epic, "head": head, "sdir": sdir, "run_dir": run_dir,
               "env": env, "proc": proc, "run_script": run_script}
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=60)
        # proc.kill() stops only Git's launcher: stop the drain, the strategy and the gate's
        # child by tree, so nothing survives the test
        for name in (run_dir / "merge-drain.pid", sdir / "child.pid"):
            text = name.read_text().strip() if name.exists() else ""
            if text.isdigit():
                kill_tree(int(text))
        kill_naming(sdir)


def test_cancel_stops_the_drain_and_restores_the_epic_worktree(drain):
    d = drain
    child = (d["sdir"] / "child.pid").read_text(encoding="utf-8").strip()
    drain_pid = (d["run_dir"] / "merge-drain.pid").read_text(encoding="utf-8").strip()
    lock = d["repo"] / ".git" / "pad-locks" / "merge"
    assert lock.is_dir() and _alive(child) and _alive(drain_pid)
    assert "pad-candidate" in git("worktree", "list", cwd=d["repo"])

    r = d["run_script"]("merge.sh", "--run", RUN, "--cancel", cwd=d["repo"], env=d["env"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.splitlines()[-1] == f"CANCELLED {RUN}"

    assert _wait(lambda: not _alive(child)), "the gate process is still running"
    assert _wait(lambda: not _alive(drain_pid)), "the drain is still running"
    assert "merge-drain.pid" not in os.listdir(d["run_dir"])
    assert "merge" not in os.listdir(d["repo"] / ".git" / "pad-locks")
    assert "pad-candidate" not in git("worktree", "list", cwd=d["repo"])
    epic = d["epic"]
    assert git("branch", "--show-current", cwd=epic) == "epic"
    assert git("rev-parse", "HEAD", cwd=epic) == d["head"]
    assert git("status", "--porcelain", cwd=epic) == ""
    has_merge_head = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=str(epic), capture_output=True
    ).returncode == 0
    assert not has_merge_head, "a merge is still in progress in the epic worktree"


def test_cancel_with_no_drain_running_says_nothing_running(repo, run_script):
    (repo / ".work" / "runs" / RUN).mkdir(parents=True)
    r = run_script("merge.sh", "--run", RUN, "--cancel", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.splitlines()[-1] == "CANCEL nothing running"
