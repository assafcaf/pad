"""render-check.sh renders one surface state to a file through the surface's Render command.

    render-check.sh --surface <name> --route <r> --viewport WxH [--state <file>] --out <png>

The command is the `Render command` cell of the surface's row in the `## Surfaces` table of
`.claude/workflow/config.md` (columns found by header name). It is a template with `{route}`,
`{viewport}`, `{width}`, `{height}`, `{state}` and `{out}` placeholders, run in the worktree.
Last line: `RENDER OK <out>` | `RENDER FAIL <surface>: <why>` (exit 1) | `RENDER NONE <surface>`
(exit 1). Exit 64 on usage. PAD assumes no web app: the fake render command here is bash.
"""
from __future__ import annotations

from pathlib import Path

import pytest

# Render command sits before Preview start, so a positional reader would get it wrong.
HEADER = "| Surface | Entry point | Render command | Preview start | Cannot show |"
SEP = "|---|---|---|---|---|"

WRITE = "printf '%s %s %s %s %s.' '{route}' '{viewport}' '{width}' '{height}' '{state}' > {out}"


def _config(repo: Path, rows: list[tuple[str, str]], header: str = HEADER) -> None:
    lines = [header, SEP]
    for name, cmd in rows:
        cell = f"`{cmd}`" if cmd else ""
        lines.append(f"| `{name}` | `app` | {cell} | `npm run dev` | `nothing` |")
    text = "# Config\n\n## Surfaces\n\nThe places.\n\n" + "\n".join(lines) + "\n\n## Review\n\n- x\n"
    cfg = repo / ".claude" / "workflow" / "config.md"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_bytes(text.encode("utf-8"))


def _last(r) -> str:
    lines = r.stdout.strip().splitlines()
    return lines[-1] if lines else ""


def _render(run_script, repo, *extra, surface="web", route="/home", viewport="390x844", out=None):
    out = out or (repo.parent / "shots" / "home.png")
    args = ["--surface", surface, "--route", route, "--viewport", viewport, "--out", out.as_posix(), *extra]
    return run_script("render-check.sh", *args, cwd=repo), out


def test_ok_fills_every_placeholder_and_writes_the_file(repo, run_script):
    _config(repo, [("web", WRITE)])
    state = repo / "state.json"
    state.write_text("{}", encoding="utf-8")

    r, out = _render(run_script, repo, "--state", state.as_posix())

    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == f"RENDER OK {out.as_posix()}"
    assert out.read_text(encoding="utf-8") == f"/home 390x844 390 844 {state.as_posix()}."


def test_runs_in_the_current_worktree(repo, worktree, run_script):
    wt = worktree(repo, "feature")
    _config(wt, [("web", "pwd > {out}")])
    sub = wt / "sub"
    sub.mkdir()

    r, out = _render(run_script, sub)

    assert r.returncode == 0, r.stdout + r.stderr
    got = out.read_text(encoding="utf-8").strip()
    assert Path(got).name == wt.name


def test_columns_are_found_by_header_name(repo, run_script):
    header = "| Render command | Cannot show | Surface | Entry point | Preview start |"
    cfg = repo / ".claude" / "workflow" / "config.md"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_bytes(
        ("## Surfaces\n\n" + header + "\n" + SEP + "\n"
         "| `printf x > {out}` | `n` | `web` | `app` | `dev` |\n").encode("utf-8"))

    r, out = _render(run_script, repo)

    assert r.returncode == 0, r.stdout + r.stderr
    assert out.read_bytes() == b"x"


def test_picks_the_named_surface(repo, run_script):
    _config(repo, [("cli", "printf cli > {out}"), ("web", "printf web > {out}")])

    r, out = _render(run_script, repo, surface="web")

    assert r.returncode == 0, r.stdout + r.stderr
    assert out.read_bytes() == b"web"


@pytest.mark.parametrize("cmd, surface, stale, needle", [
    ("printf x > {out}; exit 3", "web", False, "3"),
    ("true", "web", False, ""),
    (": > {out}", "web", False, ""),
    ("true", "web", True, ""),
    (WRITE, "mobile", False, ""),
], ids=["nonzero-exit", "missing-output", "empty-output", "stale-output-does-not-count",
        "unknown-surface"])
def test_a_render_that_produces_no_fresh_file_fails(repo, run_script, cmd, surface, stale, needle):
    _config(repo, [("web", cmd)])
    out = repo.parent / "shots" / "home.png"
    if stale:
        out.parent.mkdir(parents=True)
        out.write_bytes(b"old")

    r, _ = _render(run_script, repo, surface=surface, out=out)

    assert r.returncode == 1
    assert _last(r).startswith(f"RENDER FAIL {surface}: ")
    assert needle in _last(r)


def test_no_render_command_is_none(repo, run_script):
    _config(repo, [("web", "")])

    r, _ = _render(run_script, repo)

    assert r.returncode == 1
    assert _last(r) == "RENDER NONE web"


def test_no_render_column_is_none(repo, run_script):
    cfg = repo / ".claude" / "workflow" / "config.md"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_bytes(b"## Surfaces\n\n| Surface | Entry point |\n|---|---|\n| `web` | `app` |\n")

    r, _ = _render(run_script, repo)

    assert r.returncode == 1
    assert _last(r) == "RENDER NONE web"


def test_command_output_stays_off_the_last_line(repo, run_script):
    _config(repo, [("web", "echo noisy; printf x > {out}")])

    r, out = _render(run_script, repo)

    assert r.returncode == 0
    assert _last(r) == f"RENDER OK {out.as_posix()}"


@pytest.mark.parametrize("args", [
    [],
    ["--surface", "web", "--route", "/", "--viewport", "390x844"],
    ["--surface", "web", "--route", "/", "--viewport", "big", "--out", "x.png"],
    ["--surface", "web", "--route", "/", "--viewport", "390x844", "--out", "x.png", "--bogus", "1"],
])
def test_usage(repo, run_script, args):
    _config(repo, [("web", WRITE)])
    r = run_script("render-check.sh", *args, cwd=repo)
    assert r.returncode == 64
