"""merge-task.sh --run writes the bookkeeping itself once the merge is pushed, and --typecheck
gates the merge.

On MERGED with --run <id>: the evidence file and run-log line (render-evidence.sh), the PR-table
row on stdout, the ticket moved to done (ledger.sh) and its board.md row. A failed bookkeeping
write prints BOOKKEEPING FAIL and is logged, but the last line stays MERGED.
"""
from __future__ import annotations

import re
from pathlib import Path

from conftest import git
from test_merge_task import GOAL, PASS_GATE, PASS_LINT, _epic, _last, _task

RUN = "R1"
KEY = "E1-T1"  # a local-ledger key: .work/tickets/E1/E1-T1.md


def _merge(run_script, repo, epic_wt, red, head, *, extra=()):
    return run_script(
        "merge-task.sh", "--worktree", epic_wt.as_posix(), "--branch", "epic", *extra,
        "--gate", PASS_GATE, "--lint", PASS_LINT, KEY, red, head, GOAL, cwd=repo,
    )


def _ticket(repo: Path) -> Path:
    d = repo / ".work" / "tickets" / "E1"
    d.mkdir(parents=True)
    p = d / f"{KEY}.md"
    p.write_bytes(f"---\nkey: {KEY}\nstatus: doing\n---\n\n## Outcome\nx\n".encode())
    return p


def _runs(repo: Path) -> Path:
    return repo / ".work" / "runs" / RUN


def test_merged_with_run_writes_evidence_log_ledger_and_board(repo, worktree, run_script):
    ticket = _ticket(repo)
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, head = _task(repo, worktree, epic_head)
    r = _merge(run_script, repo, epic_wt, red, head,
               extra=("--run", RUN, "--outcomes", "O1 O2"))
    assert r.returncode == 0, r.stdout + r.stderr
    sha = git("rev-parse", "HEAD", cwd=epic_wt)
    assert _last(r) == f"MERGED {sha}"
    assert f"| {KEY} | O1 O2 | {sha[:7]} |" in r.stdout
    assert "BOOKKEEPING FAIL" not in r.stdout

    evidence = (_runs(repo) / f"{KEY}.md").read_text(encoding="utf-8")
    assert f"- Merge commit: {sha}" in evidence
    assert f"- Red commit: {red}" in evidence
    progress = (_runs(repo) / "progress.md").read_text(encoding="utf-8")
    assert f"{KEY}: done (red {red[:7]}, merge {sha[:7]})" in progress

    text = ticket.read_text(encoding="utf-8")
    assert re.search(r"^status: done$", text, re.M)
    assert f"merged {sha[:7]} into epic (run {RUN})" in text
    board = (_runs(repo) / "board.md").read_text(encoding="utf-8")
    assert f"| {KEY} | - | done | epic | {sha[:7]} | .work/runs/{RUN}/{KEY}.md |" in board
    assert not (epic_wt / ".work" / "runs").exists()


def test_failed_ledger_write_is_reported_and_logged_but_merge_stands(repo, worktree, run_script):
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, head = _task(repo, worktree, epic_head)
    r = _merge(run_script, repo, epic_wt, red, head, extra=("--run", RUN))
    assert r.returncode == 0, r.stdout + r.stderr
    sha = git("rev-parse", "HEAD", cwd=epic_wt)
    assert _last(r) == f"MERGED {sha}"
    assert f"BOOKKEEPING FAIL {KEY}: ledger: LEDGER FAIL {KEY}: no ticket at" in r.stdout
    progress = (_runs(repo) / "progress.md").read_text(encoding="utf-8")
    assert f"BOOKKEEPING FAIL {KEY}: ledger:" in progress


def test_without_run_no_bookkeeping_is_written(repo, worktree, run_script):
    _ticket(repo)
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, head = _task(repo, worktree, epic_head)
    r = _merge(run_script, repo, epic_wt, red, head)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (repo / ".work" / "runs").exists()


def test_failing_typecheck_rejects_and_leaves_epic_untouched(repo, worktree, run_script):
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, head = _task(repo, worktree, epic_head)
    r = _merge(run_script, repo, epic_wt, red, head, extra=("--typecheck", "exit 3", "--run", RUN))
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r) == f"REJECTED {KEY}: typecheck failed (exit 3)"
    assert git("rev-parse", "HEAD", cwd=epic_wt) == epic_head
    assert not (repo / ".work" / "runs" / RUN / f"{KEY}.md").exists()


def test_merged_with_run_logs_each_rule_explained_removal(repo, worktree, run_script):
    _ticket(repo)
    epic_wt = worktree(repo, "epic")
    old = epic_wt / "tests" / "test_old.py"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"def test_old():\n    assert True\n")
    git("add", "tests/test_old.py", cwd=epic_wt)
    git("commit", "-q", "-m", "epic: old test", cwd=epic_wt)
    git("push", "-q", "-u", "origin", "epic", cwd=epic_wt)
    epic_head = git("rev-parse", "HEAD", cwd=epic_wt)

    task = worktree(repo, "task")
    git("reset", "-q", "--hard", epic_head, cwd=task)
    git("rm", "-q", "tests/test_old.py", cwd=task)
    (task / "tests").mkdir(exist_ok=True)
    (task / "tests" / "test_new.py").write_bytes(
        b"# ported-from: tests/test_old.py::test_old\ndef test_new():\n    assert False\n")
    git("add", "tests/test_new.py", cwd=task)
    git("commit", "-q", "-m", f"test({KEY}): O1 [red]", cwd=task)
    red = git("rev-parse", "HEAD", cwd=task)
    (task / "src").mkdir()
    (task / "src" / "impl.py").write_bytes(b"X = 1\n")
    git("add", "src/impl.py", cwd=task)
    git("commit", "-q", "-m", f"feat({KEY}): impl", cwd=task)
    head = git("rev-parse", "HEAD", cwd=task)

    r = _merge(run_script, repo, epic_wt, red, head, extra=("--run", RUN))
    assert r.returncode == 0, r.stdout + r.stderr
    line = f"REMOVALS {KEY}: tests/test_old.py::test_old ported-from"
    assert line in r.stdout
    assert line in (_runs(repo) / "progress.md").read_text(encoding="utf-8")
