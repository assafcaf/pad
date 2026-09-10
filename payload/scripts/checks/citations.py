#!/usr/bin/env python3
"""Every ``path:line`` citation in committed Markdown must resolve.

PROJ-17's final whole-branch review, finding 1, the run's only Critical: eight durable files
cited ``docs/dispatch/PROJ-17/...``, a directory the next commit deleted. Invisible from inside
any one ticket, and found by an opus review minutes before hand-over.

The reviewer prompt in ``.claude/skills/dispatch/reviewer-prompt.md`` also records a review that
cited line 245 of a 141-line file, and every citation in it had to be re-derived by hand.

Both are this script.

Usage::

    uv run python scripts/checks/citations.py [<path> ...]

With no arguments it checks every tracked ``.md`` file. Exit 0 when every citation resolves.

Citations into upstream checkouts are *skipped*, not failed: ``vendor/`` and ``submodules/`` are
gitignored per ``CLAUDE.md`` and their line numbers cannot be checked from here. They are
reported so the count is honest.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

#: Prefixes that name an upstream checkout rather than this repo. A citation into one of these
#: is unverifiable here, which is not the same as wrong.
#: Add your own here -- any directory holding code this repo does not own.
UPSTREAM_PREFIXES = (
    "vendor/",
    "submodules/",
    "third_party/",
    "node_modules/",
)

#: Extensions worth resolving. Deliberately narrow: it keeps timestamps (``16:46:37Z``), issue
#: keys (``PROJ-17:``) and ``host:port`` out of the match set without needing a negative pattern.
EXTENSIONS = (
    "py", "sh", "md", "yaml", "yml", "toml", "json", "txt", "cfg", "ini", "lock", "env",
)

CITATION = re.compile(
    r"(?<![\w/.-])"
    r"(?P<path>(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:" + "|".join(EXTENSIONS) + r"))"
    r":(?P<start>\d+)(?:-(?P<end>\d+))?"
    r"(?![\w-])"
)


def tracked_markdown() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.md"],
        capture_output=True, text=True, check=True,
    ).stdout
    return [Path(p) for p in out.split("\0") if p]


def line_count(path: Path) -> int:
    with path.open("rb") as fh:
        return sum(1 for _ in fh)


def main(argv: list[str]) -> int:
    files = [Path(a) for a in argv] or tracked_markdown()
    root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    )

    checked = skipped = 0
    failures: list[str] = []
    cache: dict[Path, int | None] = {}

    for md in files:
        if not md.exists():
            continue
        for lineno, text in enumerate(md.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for m in CITATION.finditer(text):
                cited = m.group("path")

                if cited.startswith(UPSTREAM_PREFIXES):
                    skipped += 1
                    continue
                # A bare filename with no directory is prose more often than a citation.
                if "/" not in cited and not (root / cited).exists():
                    continue

                target = root / cited
                if target not in cache:
                    cache[target] = line_count(target) if target.is_file() else None
                total = cache[target]

                checked += 1
                if total is None:
                    failures.append(f"{md.as_posix()}:{lineno}: cites {cited} -- no such file")
                    continue
                start = int(m.group("start"))
                end = int(m.group("end") or start)
                if start < 1 or end > total:
                    failures.append(
                        f"{md.as_posix()}:{lineno}: cites {cited}:{m.group(0).split(':', 1)[1]} "
                        f"-- file has {total} lines"
                    )

    if failures:
        print(f"citations: FAIL -- {len(failures)} of {checked} citations do not resolve")
        for f in failures[:40]:
            print(f"  {f}")
        if len(failures) > 40:
            print(f"  ... and {len(failures) - 40} more")
        return 1

    tail = f", {skipped} skipped (upstream checkout)" if skipped else ""
    print(f"citations: ok -- {checked} citations resolve{tail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
