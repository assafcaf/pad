"""O26, O27: a test failing outside the change is recorded for the run; the second time it fails
that way the gate is not rerun and the test is named flaky.

The record is `<main checkout>/.work/runs/<id>/flakes`, one line `<test id> <KEY or batch> <ts>`
per failing test. merge-task.sh (--run <id>) and merge-gate.sh (--run <id>) both use it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import test_merge_gate as mg
import test_merge_task as mt
from conftest import git

# The merge-gate tests' fixture, reused here.
env = mg.env

pytestmark = pytest.mark.slow

RUN = "E9"
TEST_ID = "tests/test_other.py::test_x"
FAILED = f"FAILED {TEST_ID} - boom"


def _flakes(repo: Path) -> Path:
    return repo / ".work" / "runs" / RUN / "flakes"


def _lines(repo: Path) -> list[str]:
    p = _flakes(repo)
    return p.read_text(encoding="utf-8").splitlines() if p.exists() else []


def _seed(repo: Path, *lines: str) -> None:
    p = _flakes(repo)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(f"{ln}\n" for ln in lines), encoding="utf-8")


def _task_merge(repo, worktree, run_script, tmp_path, *, fail_times, line=FAILED, run=True):
    """Merge a task whose gate fails `fail_times` times with `line`, on an untouched test file."""
    epic_wt, _ = mt._epic(repo, worktree)
    mt._commit(epic_wt, {"tests/test_other.py": "def test_x():\n    pass\n"}, "epic: other test")
    git("push", "-q", "origin", "epic", cwd=epic_wt)
    epic_head = git("rev-parse", "HEAD", cwd=epic_wt)
    _, red, head = mt._task(repo, worktree, epic_head)
    n = tmp_path / "n.txt"
    gate = mg._flaky(n, fail_times, line) + "; " + mt.PASS_GATE
    extra = ("--run", RUN) if run else ()
    r = mt._merge(run_script, repo, epic_wt, red, head, gate=gate, extra=extra)
    return r, epic_wt, epic_head, n


# merge-task.sh ---------------------------------------------------------------------------------


def test_O26_merge_task_records_the_outside_failure_before_the_rerun(repo, worktree, run_script, tmp_path):
    r, _, _, n = _task_merge(repo, worktree, run_script, tmp_path, fail_times=1)
    assert r.returncode == 0, r.stdout + r.stderr
    assert mg._runs(n) == 2
    lines = _lines(repo)
    assert len(lines) == 1, lines
    parts = lines[0].split()
    assert parts[:2] == [TEST_ID, mt.KEY]
    assert len(parts) == 3 and parts[2]  # a timestamp


def test_O26_merge_task_records_each_failing_test(repo, worktree, run_script, tmp_path):
    line = f"{FAILED}\nFAILED tests/test_other.py::test_y - boom"
    r, _, _, n = _task_merge(repo, worktree, run_script, tmp_path, fail_times=1, line=line)
    assert r.returncode == 0, r.stdout + r.stderr
    ids = sorted(ln.split()[0] for ln in _lines(repo))
    assert ids == [TEST_ID, "tests/test_other.py::test_y"]


def test_O26_merge_task_records_nothing_for_a_failure_naming_no_test_file(repo, worktree, run_script, tmp_path):
    r, _, _, n = _task_merge(repo, worktree, run_script, tmp_path, fail_times=1, line="something broke")
    assert mt._last(r).startswith("REJECTED"), r.stdout + r.stderr
    assert mg._runs(n) == 1
    assert _lines(repo) == []


def test_O26_merge_task_without_run_records_nothing_and_still_reruns(repo, worktree, run_script, tmp_path):
    r, _, _, n = _task_merge(repo, worktree, run_script, tmp_path, fail_times=1, run=False)
    assert r.returncode == 0, r.stdout + r.stderr
    assert mg._runs(n) == 2
    assert not list((repo / ".work").glob("runs/*/flakes"))


def test_O27_merge_task_names_a_recorded_test_flaky_without_a_rerun(repo, worktree, run_script, tmp_path):
    _seed(repo, f"{TEST_ID} E2-T3 2026-10-19T10:00:00Z")
    r, epic_wt, epic_head, n = _task_merge(repo, worktree, run_script, tmp_path, fail_times=99)
    assert r.returncode == 1, r.stdout + r.stderr
    assert mt._last(r) == f"REJECTED {mt.KEY}: flaky {TEST_ID} (failed 2 times outside the change)"
    assert mg._runs(n) == 1
    mt._assert_untouched(epic_wt, repo, epic_head, r)


def test_O27_merge_task_counts_every_prior_failure(repo, worktree, run_script, tmp_path):
    _seed(repo, f"{TEST_ID} E2-T3 2026-10-19T10:00:00Z", f"{TEST_ID} batch 2026-10-19T11:00:00Z")
    r, _, _, _ = _task_merge(repo, worktree, run_script, tmp_path, fail_times=99)
    assert mt._last(r) == f"REJECTED {mt.KEY}: flaky {TEST_ID} (failed 3 times outside the change)"


def test_O27_merge_task_reruns_when_only_another_test_is_recorded(repo, worktree, run_script, tmp_path):
    _seed(repo, "tests/test_other.py::test_z E2-T3 2026-10-19T10:00:00Z")
    r, _, _, n = _task_merge(repo, worktree, run_script, tmp_path, fail_times=1)
    assert r.returncode == 0, r.stdout + r.stderr
    assert mg._runs(n) == 2


# merge-gate.sh ---------------------------------------------------------------------------------


def _gate(e):
    return e.gate("--run", RUN)


def test_O26_merge_gate_records_the_outside_failure_as_batch_before_the_rerun(env, repo, tmp_path):
    n = tmp_path / "n.txt"
    e = env(full=mg._flaky(n, 1, FAILED))
    e.commit({"src/impl.py": "X = 1\n"})
    r = _gate(e)
    assert mg._last(r) == "GATE PASS", r.stdout + r.stderr
    assert mg._runs(n) == 2
    lines = _lines(repo)
    assert len(lines) == 1, lines
    parts = lines[0].split()
    assert parts[:2] == [TEST_ID, "batch"]
    assert len(parts) == 3 and parts[2]


def test_O26_merge_gate_without_run_records_nothing_and_still_reruns(env, repo, tmp_path):
    n = tmp_path / "n.txt"
    e = env(full=mg._flaky(n, 1, FAILED))
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate()
    assert mg._last(r) == "GATE PASS", r.stdout + r.stderr
    assert mg._runs(n) == 2
    assert not list((repo / ".work").glob("runs/*/flakes"))


def test_O26_merge_gate_records_nothing_for_a_failure_naming_no_test_file(env, repo, tmp_path):
    n = tmp_path / "n.txt"
    e = env(full=mg._flaky(n, 1, "something broke"))
    e.commit({"src/impl.py": "X = 1\n"})
    r = _gate(e)
    assert mg._last(r) == "GATE FAIL", r.stdout + r.stderr
    assert _lines(repo) == []


def test_O27_merge_gate_names_a_recorded_test_flaky_without_a_rerun(env, repo, tmp_path):
    _seed(repo, f"{TEST_ID} E2-T3 2026-10-19T10:00:00Z")
    n = tmp_path / "n.txt"
    e = env(full=mg._flaky(n, 99, FAILED))
    e.commit({"src/impl.py": "X = 1\n"})
    r = _gate(e)
    assert mg._last(r) == f"GATE FLAKE {TEST_ID}", r.stdout + r.stderr
    assert r.returncode == 1
    assert mg._runs(n) == 1
