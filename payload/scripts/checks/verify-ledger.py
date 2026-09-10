#!/usr/bin/env python3
"""Every probe must have a red run and a green run.

This is the check that makes evidence mean something. A probe that has only ever been seen to
pass is a probe nobody has seen fail -- PROJ-17 shipped ``tests/test_compose.py:211-221``, which
could not fail for the flag it existed to guard, and it took an opus whole-branch review to
notice.

It is also the TDD red step, recorded. The worker is not doing two things.

Usage::

    uv run python scripts/checks/verify-ledger.py <run-id> [--task <task-id>]

Exit 0 when every probe named in the ledger has, for the task it belongs to:

* at least one ``red`` line with a non-zero exit, and
* at least one ``green`` line with exit 0 at a later timestamp,

and every line's captured output actually exists on disk.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--task", default=None, help="check one task instead of the whole run")
    ap.add_argument("--root", default=".", help="repository root")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    ledger = root / "evidence" / args.run_id / "ledger.jsonl"
    if not ledger.is_file():
        print(f"verify-ledger: FAIL -- no ledger at {ledger.relative_to(root)}")
        return 1

    runs: dict[tuple[str, str], list[dict]] = defaultdict(list)
    malformed: list[str] = []

    for n, raw in enumerate(ledger.read_text(encoding="utf-8").splitlines(), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError as exc:
            malformed.append(f"line {n}: not JSON ({exc.msg})")
            continue
        missing = [k for k in ("task", "probe", "phase", "exit", "ts") if k not in entry]
        if missing:
            malformed.append(f"line {n}: missing {', '.join(missing)}")
            continue
        if args.task and entry["task"] != args.task:
            continue
        runs[(entry["task"], entry["probe"])].append(entry | {"_line": n})

    failures = list(malformed)

    for (task, probe), entries in sorted(runs.items()):
        for e in entries:
            out = e.get("stdout_path")
            if not out:
                failures.append(f"{task} {probe} line {e['_line']}: no stdout_path")
            elif not (root / out).is_file():
                failures.append(f"{task} {probe} line {e['_line']}: stdout_path {out} is missing")

        reds = [e for e in entries if e["phase"] == "red"]
        greens = [e for e in entries if e["phase"] == "green"]

        if not reds:
            failures.append(
                f"{task} {probe}: no red run -- this probe has never been seen to fail"
            )
        elif not any(e["exit"] != 0 for e in reds):
            failures.append(
                f"{task} {probe}: red run exited 0 -- it passes without the task's change, "
                f"so it is not checking the task"
            )

        if not greens:
            failures.append(f"{task} {probe}: no green run")
        elif not any(e["exit"] == 0 for e in greens):
            failures.append(f"{task} {probe}: no green run exited 0 -- the criterion is not met")

        if reds and greens:
            last_red = max(e["ts"] for e in reds if e["exit"] != 0) if any(
                e["exit"] != 0 for e in reds
            ) else None
            first_green = min(e["ts"] for e in greens if e["exit"] == 0) if any(
                e["exit"] == 0 for e in greens
            ) else None
            if last_red and first_green and first_green < last_red:
                failures.append(
                    f"{task} {probe}: the green run predates the red run -- the pair proves nothing"
                )

    if failures:
        print(f"verify-ledger: FAIL -- {len(failures)} problem(s) in {ledger.name}")
        for f in failures[:40]:
            print(f"  {f}")
        if len(failures) > 40:
            print(f"  ... and {len(failures) - 40} more")
        return 1

    scope = f"task {args.task}" if args.task else f"run {args.run_id}"
    print(f"verify-ledger: ok -- {len(runs)} probe(s) in {scope}, each red then green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
