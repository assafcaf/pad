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


# --- protected paths and ownership ---------------------------------------------------------

def _task_on(repo, worktree, epic_head, path, *, trailer=""):
    wt = worktree(repo, "ptask")
    git("reset", "-q", "--hard", epic_head, cwd=wt)
    (wt / "tests").mkdir(exist_ok=True)
    (wt / "tests" / "test_db.py").write_bytes(b"def test_db():\n    assert False\n")
    git("add", "tests/test_db.py", cwd=wt)
    msg = f"test({KEY}): O1 [red]" + (f"\n\n{trailer}" if trailer else "")
    git("commit", "-q", "-m", msg, cwd=wt)
    red = git("rev-parse", "HEAD", cwd=wt)
    p = wt / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"X = 1\n")
    git("add", path, cwd=wt)
    git("commit", "-q", "-m", f"feat({KEY}): impl", cwd=wt)
    return red, git("rev-parse", "HEAD", cwd=wt)


def _merge_any(run_script, repo, epic_wt, red, head, extra):
    return run_script(
        "merge-task.sh", "--worktree", epic_wt.as_posix(), "--branch", "epic", *extra,
        "--gate", "true", "--lint", "true", KEY, red, head, GOAL, cwd=repo,
    )


def test_protected_diff_without_a_test_designer_red_is_rejected_needs_strict(repo, worktree, run_script):
    epic_wt, epic_head = _epic(repo, worktree)
    red, head = _task_on(repo, worktree, epic_head, "src/db/store.py")
    r = _merge_any(run_script, repo, epic_wt, red, head, ("--protected", "src/db/**"))
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r).startswith(f"REJECTED {KEY}: needs-strict (src/db/store.py is a protected path")
    assert git("rev-parse", "HEAD", cwd=epic_wt) == epic_head


def test_protected_diff_with_a_test_designer_red_merges(repo, worktree, run_script):
    epic_wt, epic_head = _epic(repo, worktree)
    red, head = _task_on(repo, worktree, epic_head, "src/db/store.py", trailer="PAD-Role: test-designer")
    r = _merge_any(run_script, repo, epic_wt, red, head, ("--protected", "src/db/**"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r).startswith("MERGED ")


def test_unprotected_diff_needs_no_trailer(repo, worktree, run_script):
    epic_wt, epic_head = _epic(repo, worktree)
    red, head = _task_on(repo, worktree, epic_head, "src/ui/page.py")
    r = _merge_any(run_script, repo, epic_wt, red, head, ("--protected", "src/db/**, src/auth/**"))
    assert r.returncode == 0, r.stdout + r.stderr


def test_ticket_is_passed_to_task_submit_ownership(repo, worktree, run_script, tmp_path):
    epic_wt, epic_head = _epic(repo, worktree)
    red, head = _task_on(repo, worktree, epic_head, "src/ui/page.py")
    ticket = tmp_path / "E1-T1.md"
    ticket.write_bytes(b"## Outcome\nx\n\n## Owns\n- src/other/\n\n## Touches\nnone\n")
    r = _merge_any(run_script, repo, epic_wt, red, head, ("--ticket", ticket.as_posix()))
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r) == f"REJECTED {KEY}: ownership: src/ui/page.py"


def test_with_run_each_result_is_logged_as_a_timestamped_event(repo, worktree, run_script):
    _ticket(repo)
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, head = _task(repo, worktree, epic_head)
    r = _merge(run_script, repo, epic_wt, red, head, extra=("--typecheck", "exit 3", "--run", RUN))
    assert r.returncode == 1
    r = _merge(run_script, repo, epic_wt, red, head, extra=("--run", RUN))
    assert r.returncode == 0, r.stdout + r.stderr
    sha = git("rev-parse", "HEAD", cwd=epic_wt)
    events = [l for l in (_runs(repo) / "progress.md").read_text(encoding="utf-8").splitlines()
              if re.match(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ ", l)]
    assert [e.split(" ", 1)[1] for e in events] == [
        f"REJECTED {KEY} typecheck failed (exit 3)",
        f"MERGED {KEY} {sha}",
    ]


def test_capture_renders_the_merged_tree_into_the_evidence_dir(repo, worktree, run_script):
    _ticket(repo)
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, head = _task(repo, worktree, epic_head)
    r = _merge(run_script, repo, epic_wt, red, head,
               extra=("--run", RUN, "--capture", "cat src/impl.py > {out}"))
    assert r.returncode == 0, r.stdout + r.stderr
    shot = _runs(repo) / "evidence" / KEY / "merged.png"
    assert shot.read_bytes().replace(b"\r\n", b"\n") == b"X = 1\n"
    assert f"EVIDENCE {KEY}: " in r.stdout


def test_a_failed_capture_is_bookkeeping_not_a_rejection(repo, worktree, run_script):
    _ticket(repo)
    epic_wt, epic_head = _epic(repo, worktree)
    _, red, head = _task(repo, worktree, epic_head)
    r = _merge(run_script, repo, epic_wt, red, head, extra=("--run", RUN, "--capture", "exit 4"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r).startswith("MERGED ")
    assert f"BOOKKEEPING FAIL {KEY}: capture: no render at" in r.stdout
