"""Status line: model, checkout, context, cost, and epic progress.

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
from datetime import datetime, timedelta, timezone
from itertools import islice
from pathlib import Path

BAR = "▁▂▃▄▅▆▇█"

# How old a progress snapshot may be before the status line stops presenting it as live.
SNAPSHOT_STALE_HOURS = 6


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


def work_dir(start: Path, *children: str) -> Path | None:
    """The nearest `.work/` at or above `start` holding one of `children`.

    `.work/` is untracked, so every checkout has its own and they hold different things: the
    epic worktree's has the run log, the main checkout's has the tickets. Walking up while
    asking for a specific child finds the right one from either place, and finds nothing in a
    project that does not use this workflow.
    """
    for base in (start, *start.parents):
        work = base / ".work"
        try:
            if any((work / child).exists() for child in children):
                return work
        except OSError:
            return None
    return None


def run_progress(project_dir: Path) -> str:
    """`PROJ-70 2/5` for the newest /batch-implement run log, when there is one.

    The run log is append-only, one line per task outcome, so counting lines is enough.
    """
    work = work_dir(project_dir, "runs")
    if work is None:
        return ""
    runs = sorted(
        work.glob("runs/*/progress.md"),
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


def ticket_status(ticket: Path) -> str:
    """The `status:` field from a local ticket's frontmatter, or "" if it has none."""
    try:
        with ticket.open(encoding="utf-8", errors="replace") as handle:
            for line in islice(handle, 12):
                match = re.match(r"status:\s*(\S+)", line)
                if match:
                    return match.group(1)
    except OSError:
        pass
    return ""


def from_tickets(tickets: Path) -> str:
    """`E2 5/7 ▶T6` counted straight from the local adapter's ticket files.

    The active epic is the one with a task in the doing status, else the lowest-numbered epic
    that is not finished. A finished epic says nothing: its own PR is the news by then.
    """
    epics = []
    try:
        entries = sorted(tickets.iterdir())
    except OSError:
        return ""
    for epic in entries:
        if not re.fullmatch(r"E\d+", epic.name) or not epic.is_dir():
            continue
        done, total, doing = 0, 0, []
        for task in sorted(epic.glob(epic.name + "-T*.md")):
            status = ticket_status(task)
            if not status:
                continue
            total += 1
            if status == "done":
                done += 1
            elif status == "doing":
                doing.append(task.stem.rsplit("-", 1)[-1])
        if total and done < total:
            epics.append((int(epic.name[1:]), epic.name, done, total, doing))
    if not epics:
        return ""
    _, key, done, total, doing = next(
        (epic for epic in sorted(epics) if epic[4]), sorted(epics)[0]
    )
    label = f"{key} {done}/{total}"
    return f"{label} ▶{','.join(doing)}" if doing else label


def from_snapshot(path: Path) -> str:
    """`PROJ-7 4/7 ▶PROJ-12` from the snapshot `/batch-implement` leaves for a remote tracker.

    A status line renders on every event, so it may never call a tracker API; the snapshot is
    the only thing it is allowed to read. One older than SNAPSHOT_STALE_HOURS, or carrying no
    timestamp, says so and drops the in-flight task, which by then is not news.
    """
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return ""
    if not isinstance(snapshot, dict):
        return ""
    epic = str(snapshot.get("epic") or "")
    try:
        done = int(snapshot.get("done", 0))
        total = int(snapshot.get("total", 0))
    except (TypeError, ValueError):
        return ""
    if not epic or done >= total:
        return ""
    label = f"{epic} {done}/{total}"
    if stale(snapshot.get("updated")):
        return f"{label} (stale)"
    doing = [str(key) for key in (snapshot.get("doing") or []) if key]
    return f"{label} ▶{','.join(doing)}" if doing else label


def stale(updated: object) -> bool:
    """True when a snapshot carries no usable timestamp, or one past the cutoff."""
    try:
        when = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return True
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - when > timedelta(hours=SNAPSHOT_STALE_HOURS)


def epic_progress(project_dir: Path) -> str:
    """The active epic's task progress from the ledger, when no run log is speaking.

    The run log only exists while a run is in flight, and only in that epic's worktree. The
    ledger is the standing record: tickets on disk under the `local` adapter, and the snapshot
    under a remote one.
    """
    work = work_dir(project_dir, "tickets", "progress.json")
    if work is None:
        return ""
    if (work / "tickets").is_dir():
        return from_tickets(work / "tickets")
    return from_snapshot(work / "progress.json")


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

    progress = run_progress(project_dir) or epic_progress(project_dir)
    if progress:
        parts.append(progress)

    print(" | ".join(parts))


if __name__ == "__main__":
    main()
