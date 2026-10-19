"""E2-T9: the shipped `single` strategy merges each queued ticket by its own gated
merge-task.sh run, in queue order (O11).

Driven through merge.sh with the run file naming `single` and the shipped strategies folder.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from conftest import BASH, BIN, git
from test_merge_strategies import write_config
from test_merge_task import _commit
from test_merge_ticket import KEY, RUN, TICKET, _setup

KEY2 = "E1-T2"


def _second_ticket(repo: Path, worktree, epic_head: str) -> tuple[str, str]:
    """A second clean ticket on its own files; -> (red, head)."""
    t = repo / ".work" / "runs" / RUN / "tickets" / f"{KEY2}.md"
    text = (TICKET.replace("{protected}", "no").replace(KEY, KEY2)
            .replace("src/impl.py", "src/impl2.py").replace("tests/test_new.py", "tests/test_new2.py"))
    t.write_bytes(text.encode("utf-8"))
    tracker = repo / ".work" / "tickets" / "E1" / f"{KEY2}.md"
    tracker.write_bytes(f"---\nkey: {KEY2}\nstatus: doing\n---\n\n## Outcome\nx\n".encode())
    wt = worktree(repo, "task2")
    git("reset", "-q", "--hard", epic_head, cwd=wt)
    red = _commit(wt, {"tests/test_new2.py": "def test_new2():\n    assert False\n"},
                  f"test({KEY2}): O1 [red]")
    head = _commit(wt, {"src/impl2.py": "Y = 1\n"}, f"feat({KEY2}): impl2")
    return red, head


def test_o11_the_shipped_single_files_validate_clean(run_script, tmp_path):
    cwd = tmp_path / "work"
    cwd.mkdir()
    write_config(cwd, "single")
    r = run_script("merge-strategies.sh", "validate", cwd=cwd)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "STRATEGY FAIL" not in r.stdout
    names = run_script("merge-strategies.sh", "list", cwd=cwd).stdout
    assert re.search(r"^single\t", names, re.M), names
    # an empty queue is a no-op pass, not a failure
    script = Path(names.split("\t")[1])
    idle = subprocess.run([BASH, script.as_posix()], cwd=str(cwd), input="", text=True,
                          capture_output=True, timeout=60,
                          env={**os.environ, "PAD_RUN": RUN, "PAD_BIN": BIN.as_posix()})
    assert idle.returncode == 0, idle.stdout + idle.stderr
    assert idle.stdout.strip() == ""


@pytest.mark.slow
def test_o11_two_clean_tickets_are_each_merged_by_their_own_run_in_queue_order(
        repo, worktree, run_script):
    epic, epic_head, red1, head1 = _setup(repo, worktree)
    red2, head2 = _second_ticket(repo, worktree, epic_head)
    run_dir = repo / ".work" / "runs" / RUN
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "merge-strategy").write_text("single\n", encoding="utf-8")
    # KEY is already waiting; --ready queues KEY2 behind it and drains both.
    (run_dir / "merge-queue").write_text(f"{KEY} {head1} {red1}\n", encoding="utf-8")
    r = run_script("merge.sh", "--run", RUN, "--ready", KEY2, head2, red2, cwd=repo)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    merged = re.findall(r"^MERGED (\S+) ([0-9a-f]{40})$", r.stdout, re.M)
    assert [k for k, _ in merged] == [KEY, KEY2], out
    assert "REJECTED" not in out and "CONFLICT" not in out and "ERROR" not in out, out
    subjects = git("log", "--merges", "--reverse", "--format=%s", f"{epic_head}..HEAD",
                   cwd=epic).splitlines()
    assert [s.split(":")[0] for s in subjects] == [f"Merge {KEY}", f"Merge {KEY2}"], subjects
    assert git("rev-parse", "HEAD", cwd=epic) == merged[-1][1]
    assert git("rev-parse", "HEAD~1", cwd=epic) == merged[0][1]
    assert (epic / "src" / "impl.py").exists() and (epic / "src" / "impl2.py").exists()
