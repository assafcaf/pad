"""run-stats.sh summarises a run from the timestamped lines of its progress.md.

    run-stats.sh --run <id>

Lines `<ISO ts> <event> [<KEY>] [text]` count; every other line is ignored. Events: dispatch,
READY, MERGED, CONFLICT, REJECTED, FAILED, NEEDS_RULING, replan, turn. Output: `STAT <name>
<value>` lines, last line `STATS <run> <tickets> tickets`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

RUN = "E7"

LOG = """\
# Run E7
2026-10-15T10:00:00Z turn start
2026-10-15T10:00:05Z dispatch E7-T1 ticket .work/tickets/E7/E7-T1.md
2026-10-15T10:00:06Z dispatch E7-T2
E7-T0: done (red 1111111, merge 2222222)
2026-10-15T10:05:00Z turn
2026-10-15T10:20:00Z READY E7-T1 abc1234
2026-10-15T10:21:00Z CONFLICT E7-T1 src/app.ts
2026-10-15T10:30:00Z READY E7-T1 abc5678
2026-10-15T10:30:05Z MERGED E7-T1 def0000
2026-10-15T10:31:00Z turn
2026-10-15T11:00:00Z READY E7-T2 aaa1111
2026-10-15T11:01:00Z REJECTED E7-T2 needs-strict
2026-10-15T11:10:00Z READY E7-T2 aaa2222
2026-10-15T11:20:00Z READY E7-T2 aaa3333
2026-10-15T11:20:06+00:00 MERGED E7-T2 bbb0000
2026-10-15T11:25:00Z replan E7-T3 split from E7-T2
2026-10-15T13:30:00+02:00 dispatch E7-T3
2026-10-15T11:40:00Z FAILED E7-T3 cannot build
2026-10-15T11:41:00Z NEEDS_RULING E7-T3 which API?
2026-10-15T11:45:00Z turn
not-a-time MERGED E7-T9 x
"""


def _write(main: Path, text: str) -> None:
    d = main / ".work" / "runs" / RUN
    d.mkdir(parents=True, exist_ok=True)
    (d / "progress.md").write_bytes(text.encode("utf-8"))


def _stats(r) -> dict[str, str]:
    out = {}
    for line in r.stdout.splitlines():
        if line.startswith("STAT "):
            _, name, value = line.split(" ", 2)
            out[name] = value
    return out


def _last(r) -> str:
    lines = r.stdout.strip().splitlines()
    return lines[-1] if lines else ""


def test_counts_and_times(repo, run_script):
    _write(repo, LOG)

    r = run_script("run-stats.sh", "--run", RUN, cwd=repo)

    assert r.returncode == 0, r.stdout + r.stderr
    s = _stats(r)
    assert _last(r) == f"STATS {RUN} 3 tickets"
    assert s["turns"] == "4"
    assert s["tickets"] == "3"
    assert s["merged"] == "2"
    assert s["conflicts"] == "1"
    assert s["rejections"] == "1"
    assert s["failures"] == "1"
    assert s["rulings"] == "1"
    assert s["replans"] == "1"
    assert s["rework"] == "3"                     # T1: 2 READY -> 1, T2: 3 READY -> 2
    assert s["rework.E7-T1"] == "1"
    assert s["rework.E7-T2"] == "2"
    assert s["wall.E7-T1"] == "1800"              # 10:00:05 -> 10:30:05
    assert s["wall.E7-T2"] == "4800"              # 10:00:06 -> 11:20:06 (+00:00)
    assert "wall.E7-T3" not in s                  # never merged
    assert s["open"] == "1"
    assert s["critical_path"] == "E7-T2"
    assert s["critical_path_seconds"] == "4800"
    assert s["span_seconds"] == str(int(1.75 * 3600))   # 10:00:00 -> 11:45:00


def test_untimestamped_lines_are_ignored(repo, run_script):
    _write(repo, "E7-T1: done (red 1, merge 2)\nMERGED E7-T1 x\n")

    r = run_script("run-stats.sh", "--run", RUN, cwd=repo)

    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == f"STATS {RUN} 0 tickets"
    assert _stats(r)["turns"] == "0"


def test_crlf_and_fractional_seconds(repo, run_script):
    _write(repo, "2026-10-15T10:00:00.250Z dispatch K-1\r\n2026-10-15T10:01:00.900Z MERGED K-1 x\r\n")

    r = run_script("run-stats.sh", "--run", RUN, cwd=repo)

    assert r.returncode == 0, r.stdout + r.stderr
    assert _stats(r)["wall.K-1"] == "60"


def test_works_from_a_linked_worktree(repo, worktree, run_script):
    _write(repo, LOG)
    wt = worktree(repo, "epic")

    r = run_script("run-stats.sh", "--run", RUN, cwd=wt)

    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == f"STATS {RUN} 3 tickets"


def test_missing_progress_fails(repo, run_script):
    r = run_script("run-stats.sh", "--run", RUN, cwd=repo)
    assert r.returncode == 1


@pytest.mark.parametrize("args", [[], ["--run"], ["--run", RUN, "extra"]])
def test_usage(repo, run_script, args):
    r = run_script("run-stats.sh", *args, cwd=repo)
    assert r.returncode == 64
