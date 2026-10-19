"""E2-T18: merge.sh keeps a pass's tickets in the merge queue until the pass ends (O33).

The strategy fixture snapshots the queue file at the start of every pass into `snap`, and on the
first pass queues one more ticket with `merge.sh --ready` (a drain is running, so it only queues).
"""
from __future__ import annotations

import pytest

from conftest import BIN

from test_merge_engine import Env, RUN


@pytest.fixture
def env(repo, tmp_path, run_script):
    return Env(repo, tmp_path, run_script)


SCRIPT = """#!/usr/bin/env bash
D="{d}"
in="$(cat)"
echo "keys=$(printf '%s\n' "$in" | awk '{{print $1}}' | tr '\n' ',')" >> "$D/log"
{{ echo "--pass"; awk '{{print $1}}' "$(cat "$D/queuefile")"; }} >> "$D/snap"
if [ -e "$D/late" ]; then
  rm -f "$D/late"
  bash "{merge}" --run "{run}" --ready LATE "$(cat "$D/head")" "$(cat "$D/red")" >> "$D/late.out" 2>&1
fi
while read -r k h r; do
  [ -n "$k" ] && echo "REJECTED $k: fixture"
done <<<"$in"
exit 0
"""


def _setup(env: Env) -> None:
    env.strategy("pass")
    (env.sdir / "pass.sh").write_text(
        SCRIPT.format(d=env.sdir.as_posix(), merge=(BIN / "merge.sh").as_posix(), run=RUN),
        encoding="utf-8", newline="\n")
    (env.sdir / "queuefile").write_text(env.queue.as_posix(), encoding="utf-8")
    (env.sdir / "head").write_text(env.head, encoding="utf-8")
    (env.sdir / "red").write_text(env.red, encoding="utf-8")
    env.run_file("pass")


def _passes(env: Env) -> list[list[str]]:
    out: list[list[str]] = []
    for line in (env.sdir / "snap").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line == "--pass":
            out.append([])
        elif line:
            out[-1].append(line)
    return out


def test_pass_tickets_stay_in_queue_during_pass_and_leave_when_it_ends(env):
    """O33: both tickets' heads are in the queue while the strategy runs; later only LATE stays."""
    _setup(env)
    (env.sdir / "late").write_text("", encoding="utf-8")
    env.queue.write_text(f"B1 {env.head} {env.red}\nB2 {env.head} {env.red}\n", encoding="utf-8")
    r = env.ready("B3")
    assert r.returncode == 0, r.stdout + r.stderr
    passes = _passes(env)
    assert passes[0] == ["B1", "B2", "B3"]
    assert passes[1] == ["LATE"]
    assert env.queue_empty()
    assert "REJECTED LATE" in r.stdout


def test_ticket_queued_during_pass_is_not_lost_when_pass_ends(env):
    """O33: a --ready during the pass stays for the next pass, which runs it."""
    _setup(env)
    (env.sdir / "late").write_text("", encoding="utf-8")
    r = env.ready("A")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (env.sdir / "log").read_text(encoding="utf-8").splitlines() == ["keys=A,", "keys=LATE,"]
    assert _passes(env) == [["A"], ["LATE"]]
    assert env.queue_empty()
