"""E3-T3: the `batch` strategy under a `## Test regime` gates its candidate with the fast tier (O20, O24).

Driven like test_strategy_batch: batch.sh with a copy of bin whose merge-gate.sh logs its call and
answers GATE PASS. With tiers the call is `--gate fast --tickets <the keys of the candidate>`;
with `Tiers: none` it is today's `--gate full`.
"""
from __future__ import annotations

import re

import pytest

from conftest import git
from test_merge_gate_tiers import REGIME
from test_strategy_batch import Batch, make  # noqa: F401  (the fixture)

pytestmark = pytest.mark.slow


def _with_regime(b: Batch, *, tiers_none: bool) -> None:
    cfg = b.repo / ".claude" / "workflow" / "config.md"
    text = cfg.read_text(encoding="utf-8")
    cfg.write_bytes((text + REGIME.format(tiers="Tiers: none\n" if tiers_none else "", budget=600)).encode("utf-8"))


def test_o20_a_batch_candidate_is_gated_with_the_fast_tier_and_names_its_tickets(make):
    b = make(count=3, gate_override="echo GATE PASS")
    _with_regime(b, tiers_none=False)
    r = b.run()
    assert r.returncode == 0, r.stdout + r.stderr
    calls = b.calls("merge-gate.sh")
    assert len(calls) == 1, calls
    assert re.search(r"--gate fast\b", calls[0]), calls
    m = re.search(r"--tickets (\S+)", calls[0])
    assert m and m.group(1).split(",") == b.keys, calls
    assert len(git("log", "--merges", "--format=%s", cwd=b.epic).splitlines()) == 3


def test_o24_a_batch_under_tiers_none_keeps_the_full_gate(make):
    b = make(count=2, gate_override="echo GATE PASS")
    _with_regime(b, tiers_none=True)
    r = b.run()
    assert r.returncode == 0, r.stdout + r.stderr
    calls = b.calls("merge-gate.sh")
    assert len(calls) == 1 and re.search(r"--gate full\b", calls[0]), calls
    assert "--gate fast" not in calls[0], calls
    # the call also names the tickets, so one gate serves both regimes
    assert re.search(r"--tickets \S*E1-T1", calls[0]), calls
