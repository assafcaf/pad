"""E1-T24 O38: knowledge-paths.sh fails on a Surfaces entry point or a Git moves script that
does not resolve. Fixtures build a config.md in a throwaway repo; the script is run for real."""
from __future__ import annotations

from pathlib import Path

import pytest

SCRIPT = "knowledge-paths.sh"

SURFACE_HEADER = (
    "| Surface | Entry point | Test drives it by | Person looks by | Automated check | "
    "Preview start | Ready when | Restart when changed | Cannot show |\n"
    "|---|---|---|---|---|---|---|---|---|\n"
)
MOVES_HEADER = "| Capability | Command |\n|---|---|\n"


def surface_row(name: str, entry: str) -> str:
    return f"| `{name}` | {entry} | a | b | c | d | e | f | g |\n"


def write_config(root: Path, surfaces: list[tuple[str, str]] = (), moves: list[tuple[str, str]] = (),
                 mode: str = "off") -> None:
    text = f"## Project knowledge\n\nMode: {mode}\n\n## Surfaces\n\n" + SURFACE_HEADER
    text += "".join(surface_row(n, e) for n, e in surfaces)
    text += "\n## Git moves\n\n" + MOVES_HEADER
    text += "".join(f"| `{c}` | `{cmd}` |\n" for c, cmd in moves)
    text += "\n## Serial resources\n\nNone.\n"
    cfg = root / ".claude" / "workflow" / "config.md"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(text, encoding="utf-8")


def touch(root: Path, rel: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x\n", encoding="utf-8")


def run(run_script, root: Path):
    return run_script(SCRIPT, "--root", root.as_posix(), cwd=root)


@pytest.mark.parametrize("files, surfaces, moves, mode, ok, named, unnamed", [
    pytest.param([], [("web", "`web/index.html`")], [], "off", False, "web/index.html", None,
                 id="unresolved-surface-fails-with-knowledge-mode-off"),
    pytest.param(["CONTEXT.md", ".claude/workflow/project.md"], [("web", "`web/index.html`")],
                 [], "on", False, "web/index.html", None,
                 id="unresolved-surface-fails-with-knowledge-mode-on"),
    pytest.param(["web/index.html"], [("web", "`web/index.html`")], [], "off", True, None, None,
                 id="resolved-surface-passes"),
    pytest.param([], [("cli", "`bash bin/tool.sh --help`")], [], "off", False, "bin/tool.sh",
                 None, id="command-entry-naming-missing-script-fails"),
    pytest.param(["bin/tool.sh"], [("cli", "`bash bin/tool.sh --help`")], [], "off", True, None,
                 None, id="command-entry-naming-existing-script-passes"),
    pytest.param([], [("web", "`http://localhost:3000/app`")], [], "off", True, None, None,
                 id="url-entry-is-not-a-path"),
    pytest.param([], [("<name>", "`<url, command or file>`")], [], "off", True, None, None,
                 id="example-placeholder-row-is-not-a-path"),
    pytest.param(["web/index.html"], [("web", "`web/index.html`"), ("api", "`api/server.py`")],
                 [], "off", False, "api/server.py", "web/index.html",
                 id="only-the-unresolved-surface-is-named"),
    pytest.param([], [], [("take-red", "bash .claude/workflow/bin/take-red.sh <sha>")], "off",
                 False, ".claude/workflow/bin/take-red.sh", None,
                 id="unresolved-git-moves-script-fails"),
    pytest.param([".claude/workflow/bin/take-red.sh"], [],
                 [("take-red", "bash .claude/workflow/bin/take-red.sh <sha>")], "off", True, None,
                 None, id="resolved-git-moves-script-passes"),
    pytest.param([], [], [
        ("move-onto-sha", "git reset --hard <sha>"),
        ("discard-changes", "git checkout -- <path>"),
        ("push-epic", "git push origin <branch>"),
    ], "off", True, None, None, id="plain-git-commands-are-not-paths"),
])
def test_o38_entry_points_and_move_scripts_must_resolve(repo, run_script, files, surfaces, moves,
                                                        mode, ok, named, unnamed):
    for rel in files:
        touch(repo, rel)
    write_config(repo, surfaces=surfaces, moves=moves, mode=mode)
    r = run(run_script, repo)
    assert r.returncode == (0 if ok else 1), r.stdout + r.stderr
    if named:
        assert named in r.stdout
    if unnamed:
        assert unnamed not in r.stdout
