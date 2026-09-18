"""Status line: model, checkout, context, cost, and any live /batch-implement run.

Claude Code pipes session JSON to stdin and prints the first line of stdout under the prompt.
Installed per machine by /setup-workflow, which writes an absolute path into
`.claude/settings.local.json` (gitignored) — this file is committed, that setting is not.

Run it by hand with a sample payload:

    echo '{"model":{"display_name":"Opus"}}' | python3 .claude/statusline.py

Keep it fast and silent: it runs on every event, and anything it prints to stderr is invisible.
Missing fields are normal before the first API response, so every read has a fallback.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

BAR = "▁▂▃▄▅▆▇█"


def get(d: object, *path: str, default: object = None) -> object:
    for key in path:
        if not isinstance(d, dict) or key not in d:
            return default
        d = d[key]
    return d if d is not None else default


def branch(cwd: Path, fallback: str) -> str:
    """The checked-out branch, or the worktree name the payload already knows."""
    try:
        out = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=2,
        )
        name = out.stdout.strip()
        if name:
            return name
    except (OSError, subprocess.SubprocessError):
        pass
    return fallback


def run_progress(project_dir: Path) -> str:
    """`PROJ-70 2/5` for the newest /batch-implement run log, when there is one.

    The run log is append-only, one line per task outcome, so counting lines is enough.
    """
    runs = sorted(
        project_dir.glob(".work/runs/*/progress.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not runs:
        return ""
    log = runs[0]
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    done = len(re.findall(r"^\S+: done\b", text, re.MULTILINE))
    stuck = len(re.findall(r"^\S+: (failed|blocked)\b", text, re.MULTILINE))
    total = len(re.findall(r"^\S+: (done|failed|blocked|doing)\b", text, re.MULTILINE))
    if not total:
        return ""
    label = f"{log.parent.name} {done}/{total}"
    return f"{label} ✗{stuck}" if stuck else label


def main() -> None:
    # Windows consoles default to a codepage that cannot encode the bar glyphs, and an
    # exception here would leave the status line blank with no visible error.
    for stream in (sys.stdout, sys.stdin):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    cwd = Path(str(get(payload, "workspace", "current_dir", default="."))).resolve()
    project_dir = Path(str(get(payload, "workspace", "project_dir", default=cwd)))

    parts = [str(get(payload, "model", "display_name", default="claude"))]
    parts.append(branch(cwd, str(get(payload, "workspace", "git_worktree", default=cwd.name))))

    pct = get(payload, "context_window", "used_percentage", default=0)
    try:
        pct_int = max(0, min(100, int(float(str(pct)))))
    except ValueError:
        pct_int = 0
    parts.append(f"{BAR[min(pct_int * len(BAR) // 100, len(BAR) - 1)]} {pct_int}% ctx")

    cost = get(payload, "cost", "total_cost_usd", default=0)
    try:
        if float(cost) >= 0.01:
            parts.append(f"${float(cost):.2f}")
    except (TypeError, ValueError):
        pass

    if not get(payload, "prompt_cache", "warm", default=True):
        parts.append("cache cold")

    progress = run_progress(project_dir)
    if progress:
        parts.append(progress)

    print(" | ".join(parts))


if __name__ == "__main__":
    main()
