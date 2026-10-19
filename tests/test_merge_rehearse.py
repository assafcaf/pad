"""E2-T11 O19: `merge-strategies.sh rehearse <name>` proves a strategy's control flow and that it
keeps the engine's contract, in a scratch repo with fixture gates.

The rehearsal drives a green batch, a conflict and a red ticket and prints `STEP <name> PASS|FAIL`
per step, then `REHEARSAL OK` (exit 0) or `REHEARSAL FAILED ...` (non-zero). Step names are the
implementer's, but the three scenarios appear in them as the words green, conflict and red.
"""
from __future__ import annotations

import os
import re
import subprocess

import pytest

from conftest import BASH, BIN

STEP_LINE = re.compile(r"^STEP (\S+) (PASS|FAIL)(?: .*)?$")

# A fixture strategy that lands each ticket with a plain `git merge`, bypassing merge-task.sh.
BAD_MD = """---
name: plainmerge
script: plainmerge.sh
description: Fixture that lands with a plain git merge.
---

Breaks the engine contract on purpose.
"""
BAD_SH = """#!/usr/bin/env bash
while read -r key head red _; do
  [ -n "${key:-}" ] || continue
  git -C "$PAD_EPIC_WORKTREE" merge --no-ff -m "plain $key" "$head" >/dev/null 2>&1
  echo "MERGED $key $(git -C "$PAD_EPIC_WORKTREE" rev-parse HEAD)"
done
"""


def _rehearse(name, cwd, env=None):
    full = dict(os.environ)
    full.update(env or {})
    return subprocess.run([BASH, (BIN / "merge-strategies.sh").as_posix(), "rehearse", name],
                          cwd=str(cwd), env=full, capture_output=True, text=True,
                          encoding="utf-8", check=False, timeout=540)


def _steps(out):
    return [m.groups() for m in map(STEP_LINE.match, out.splitlines()) if m]


@pytest.mark.slow
@pytest.mark.parametrize("name", ["single", "batch"])
def test_o19_rehearsing_a_shipped_strategy_prints_steps_and_rehearsal_ok(name, tmp_path):
    r = _rehearse(name, tmp_path)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert "REHEARSAL OK" in r.stdout, out
    assert "REHEARSAL FAILED" not in r.stdout, out
    steps = _steps(r.stdout)
    assert steps, out
    assert all(status == "PASS" for _, status in steps), out
    joined = " ".join(n for n, _ in steps).lower()
    for scenario in ("green", "conflict", "red"):
        assert scenario in joined, f"no step for the {scenario} scenario: {steps}"


@pytest.mark.slow
def test_o19_a_strategy_landing_with_plain_git_merge_fails_the_rehearsal(tmp_path):
    sdir = tmp_path / "strategies"
    sdir.mkdir()
    (sdir / "plainmerge.md").write_text(BAD_MD, encoding="utf-8")
    (sdir / "plainmerge.sh").write_bytes(BAD_SH.encode("utf-8"))
    work = tmp_path / "work"
    work.mkdir()
    r = _rehearse("plainmerge", work, {"PAD_STRATEGIES_DIR": str(sdir)})
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert "REHEARSAL FAILED" in r.stdout, out
    assert "REHEARSAL OK" not in r.stdout, out
    # the broken check from the engine contract (O4) is named
    assert re.search(r"ERROR \S+: ", out), out
    assert any(status == "FAIL" for _, status in _steps(r.stdout)), out


@pytest.mark.slow
def test_o19_rehearsing_an_unknown_strategy_is_refused(tmp_path):
    r = _rehearse("no-such-strategy", tmp_path)
    out = r.stdout + r.stderr
    assert r.returncode != 0, out
    assert "REHEARSAL OK" not in r.stdout, out
    assert "no-such-strategy" in out, out
