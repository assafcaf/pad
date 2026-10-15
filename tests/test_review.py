"""review.sh writes a wave review packet from a run's board.md and evidence.

    review.sh --run <id> [--since <n>]

Writes <main>/.work/runs/<id>/review-<n>.md and review-<n>.html (n = next free number): the done
rows merged since the previous packets, a render pair per key, each key's evidence lines, and an
Unverified list. Last line `REVIEW <path to md>`. It sends no notification.
"""
from __future__ import annotations

from pathlib import Path

import pytest

RUN = "E7"
HEADER = "| Key | Owner | Status | Branch | Sha | Evidence |\n|---|---|---|---|---|---|\n"


def _rundir(main: Path) -> Path:
    d = main / ".work" / "runs" / RUN
    d.mkdir(parents=True, exist_ok=True)
    return d


def _board(main: Path, rows: list[tuple[str, str, str, str]]) -> None:
    body = "".join(f"| {k} | owner-{k} | {s} | b/{k} | {sha} | {ev} |\n" for k, s, sha, ev in rows)
    (_rundir(main) / "board.md").write_bytes((f"# Board: {RUN}\n\n" + HEADER + body).encode("utf-8"))


def _evidence(main: Path, key: str) -> None:
    (_rundir(main) / f"{key}.md").write_bytes(
        f"# {key}\n\n- Outcomes: O1\n- Merge commit: abc{key}\n- Green gate: pytest -> 3 passed\n".encode("utf-8"))


def _pair(main: Path, key: str, verdict: str | None = None, app: bool = True) -> None:
    d = _rundir(main) / "evidence" / key
    d.mkdir(parents=True, exist_ok=True)
    (d / "reference.png").write_bytes(b"\x89PNGref")
    if app:
        (d / "app.png").write_bytes(b"\x89PNGapp")
    if verdict:
        (d / "verdict.md").write_bytes(verdict.encode("utf-8"))


def _last(r) -> str:
    lines = r.stdout.strip().splitlines()
    return lines[-1] if lines else ""


def _review(run_script, cwd, *extra):
    return run_script("review.sh", "--run", RUN, *extra, cwd=cwd)


def _section(text: str, heading: str) -> str:
    part = text.split(heading, 1)[1]
    return part.split("\n## ", 1)[0]


def test_first_packet_lists_done_rows_pairs_evidence_and_unverified(repo, run_script):
    _board(repo, [("E7-T1", "done", "1111111", "E7-T1.md"),
                  ("E7-T2", "done", "2222222", "-"),
                  ("E7-T3", "doing", "-", "-")])
    _evidence(repo, "E7-T1")
    _pair(repo, "E7-T1", verdict="MATCH: header and list as in the mock\n")

    r = _review(run_script, repo)

    assert r.returncode == 0, r.stdout + r.stderr
    md = _rundir(repo) / "review-1.md"
    assert _last(r) == f"REVIEW {md.as_posix()}"
    text = md.read_text(encoding="utf-8")
    assert "notification" in text.split("\n## ", 1)[0].lower()

    merged = _section(text, "## Merged")
    assert "E7-T1" in merged and "1111111" in merged
    assert "E7-T2" in merged and "2222222" in merged
    assert "E7-T3" not in merged

    assert "](evidence/E7-T1/reference.png)" in text
    assert "](evidence/E7-T1/app.png)" in text
    assert "MATCH: header and list as in the mock" in text
    assert "- Green gate: pytest -> 3 passed" in text

    unverified = _section(text, "## Unverified")
    assert "E7-T2" in unverified       # done, no evidence file
    assert "E7-T3" in unverified       # not done
    assert "E7-T1" not in unverified


def test_html_has_the_same_content_with_images_side_by_side(repo, run_script):
    _board(repo, [("E7-T1", "done", "1111111", "E7-T1.md")])
    _evidence(repo, "E7-T1")
    _pair(repo, "E7-T1", verdict="MATCH <ok> & fine\n")

    r = _review(run_script, repo)

    assert r.returncode == 0, r.stdout + r.stderr
    html = (_rundir(repo) / "review-1.html").read_text(encoding="utf-8")
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert 'src="evidence/E7-T1/reference.png"' in html
    assert 'src="evidence/E7-T1/app.png"' in html
    assert "1111111" in html
    assert "MATCH &lt;ok&gt; &amp; fine" in html
    assert "<link" not in html and "<script" not in html


def test_second_packet_lists_only_keys_merged_since(repo, run_script):
    _board(repo, [("E7-T1", "done", "1111111", "-"), ("E7-T2", "doing", "-", "-")])
    _evidence(repo, "E7-T1")
    assert _review(run_script, repo).returncode == 0

    _board(repo, [("E7-T1", "done", "1111111", "-"), ("E7-T2", "done", "2222222", "-")])
    _evidence(repo, "E7-T2")
    r = _review(run_script, repo)

    assert r.returncode == 0, r.stdout + r.stderr
    md = _rundir(repo) / "review-2.md"
    assert _last(r) == f"REVIEW {md.as_posix()}"
    merged = _section(md.read_text(encoding="utf-8"), "## Merged")
    assert "E7-T2" in merged
    assert "E7-T1" not in merged


def test_since_zero_lists_everything_again(repo, run_script):
    _board(repo, [("E7-T1", "done", "1111111", "-")])
    _evidence(repo, "E7-T1")
    assert _review(run_script, repo).returncode == 0

    r = _review(run_script, repo, "--since", "0")

    assert r.returncode == 0, r.stdout + r.stderr
    merged = _section((_rundir(repo) / "review-2.md").read_text(encoding="utf-8"), "## Merged")
    assert "E7-T1" in merged


def test_incomplete_render_pair_is_unverified(repo, run_script):
    _board(repo, [("E7-T1", "done", "1111111", "-")])
    _evidence(repo, "E7-T1")
    _pair(repo, "E7-T1", app=False)

    r = _review(run_script, repo)

    assert r.returncode == 0, r.stdout + r.stderr
    unverified = _section((_rundir(repo) / "review-1.md").read_text(encoding="utf-8"), "## Unverified")
    assert "E7-T1" in unverified


def test_works_from_a_linked_worktree(repo, worktree, run_script):
    wt = worktree(repo, "epic")
    _board(repo, [("E7-T1", "done", "1111111", "-")])
    _evidence(repo, "E7-T1")

    r = _review(run_script, wt)

    assert r.returncode == 0, r.stdout + r.stderr
    assert (_rundir(repo) / "review-1.md").is_file()
    assert not (wt / ".work").exists()


def test_no_board_fails(repo, run_script):
    r = _review(run_script, repo)
    assert r.returncode == 1
    assert _last(r).startswith("REVIEW FAIL")


@pytest.mark.parametrize("args", [[], ["--run"], ["--run", RUN, "--since", "x"], ["--run", RUN, "--x", "1"]])
def test_usage(repo, run_script, args):
    r = run_script("review.sh", *args, cwd=repo)
    assert r.returncode == 64
