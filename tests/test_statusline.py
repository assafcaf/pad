"""statusline.py shows the active run's progress from its board.md, falling back as before.

`ledger.sh --run` keeps `.work/runs/<run>/board.md`, one row per ticket:
`| Key | Owner | Status | Branch | Sha | Evidence |`. The status line counts it (done/total,
and the tickets in flight); without a board it reads the run log or the ledger as it did.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from conftest import PAYLOAD

SCRIPT = PAYLOAD / "claude" / "statusline.py"

BOARD_HEAD = "# Board: {run}\n\n| Key | Owner | Status | Branch | Sha | Evidence |\n|---|---|---|---|---|---|\n"


def board(project: Path, run: str, rows: list[tuple[str, str]]) -> Path:
    path = project / ".work" / "runs" / run / "board.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = BOARD_HEAD.format(run=run) + "".join(
        f"| {key} | a1b2 | {status} | - | - | - |\n" for key, status in rows
    )
    path.write_bytes(body.encode("utf-8"))
    return path


def status_line(project: Path, cwd: Path | None = None) -> str:
    payload = {
        "model": {"display_name": "Opus"},
        "workspace": {"current_dir": str(cwd or project), "project_dir": str(project)},
    }
    env = dict(os.environ)
    env["TEMP"] = env["TMP"] = env["TMPDIR"] = str(project / "tmp")
    (project / "tmp").mkdir(exist_ok=True)
    out = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=30,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def progress(line: str) -> str:
    return line.split(" | ")[-1]


def test_board_counts_done_over_total_and_lists_doing(tmp_path):
    board(tmp_path, "E2", [("E2-T1", "done"), ("E2-T2", "doing"), ("E2-T3", "todo"),
                           ("E2-T4", "doing"), ("E2-T5", "done")])
    assert progress(status_line(tmp_path)) == "E2 2/5 ▶E2-T2,E2-T4"


def test_board_with_nothing_in_flight_shows_only_the_count(tmp_path):
    board(tmp_path, "E3", [("E3-T1", "done"), ("E3-T2", "done")])
    assert progress(status_line(tmp_path)) == "E3 2/2"


def test_board_is_found_from_a_worktree_inside_the_main_checkout(tmp_path):
    board(tmp_path, "E2", [("E2-T1", "done"), ("E2-T2", "doing")])
    wt = tmp_path / ".claude" / "worktrees" / "E2"
    wt.mkdir(parents=True)
    assert progress(status_line(wt)) == "E2 1/2 ▶E2-T2"


def test_the_newest_board_is_the_active_run(tmp_path):
    old = board(tmp_path, "E1", [("E1-T1", "done")])
    past = time.time() - 3600
    os.utime(old, (past, past))
    board(tmp_path, "E2", [("E2-T1", "doing"), ("E2-T2", "todo")])
    assert progress(status_line(tmp_path)) == "E2 0/2 ▶E2-T1"


def test_board_wins_over_the_run_log(tmp_path):
    board(tmp_path, "E2", [("E2-T1", "done"), ("E2-T2", "doing"), ("E2-T3", "todo")])
    log = tmp_path / ".work" / "runs" / "E2" / "progress.md"
    log.write_bytes(b"E2-T1: done\n")
    assert progress(status_line(tmp_path)) == "E2 1/3 ▶E2-T2"


def test_an_empty_board_falls_back_to_the_run_log(tmp_path):
    board(tmp_path, "E2", [])
    log = tmp_path / ".work" / "runs" / "E2" / "progress.md"
    log.write_bytes(b"E2-T1: done\nE2-T2: failed\n")
    assert progress(status_line(tmp_path)) == "E2 1/2 ✗1"


def test_no_run_files_shows_no_progress(tmp_path):
    line = status_line(tmp_path)
    assert line.startswith("Opus | ")
    assert "/" not in progress(line)


def test_a_crlf_board_still_counts(tmp_path):
    path = board(tmp_path, "E4", [("E4-T1", "done"), ("E4-T2", "doing")])
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert progress(status_line(tmp_path)) == "E4 1/2 ▶E4-T2"
