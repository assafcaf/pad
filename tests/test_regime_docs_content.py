"""E3-T4 O44: decision 0007 records the test regime's decisions with the handoff's numbers.

Content test: the record is the product. The numbers come from the handoff
(docs/2026-10-20-pad-handoff-tiers-wrapper-suite-owner.md) and the spec's Decisions: per-test
kill 60/300/900 s, memory cap 85 %, one classifying rerun, 3 reruns per selection and 12 per
ticket, flaky quarantine 8 tests / 7 days / 48 h / 100 consecutive passes.
"""
from __future__ import annotations

import re

from conftest import ROOT

DECISION = ROOT / "docs" / "decisions" / "0007-test-regime.md"


def _text() -> str:
    assert DECISION.is_file(), f"{DECISION} missing"
    return " ".join(DECISION.read_text(encoding="utf-8").split())


def test_o44_the_record_follows_the_decision_format():
    raw = DECISION.read_text(encoding="utf-8") if DECISION.is_file() else ""
    lines = raw.splitlines()
    assert lines and re.match(r"# 0007\. .*", lines[0]), lines[:1]
    assert re.search(r"^Date: \d{4}-\d{2}-\d{2} · Status: ", raw, re.M)
    assert "\n## Context\n" in raw and "\n## Decision\n" in raw


def test_o44_it_records_the_per_test_kill_and_the_cap_numbers():
    text = _text()
    assert re.search(r"60\s*/\s*300\s*/\s*900", text) or all(n in text for n in ("60 s", "300 s", "900 s"))
    assert "85%" in text or "85 %" in text


def test_o44_it_records_the_rerun_and_fix_loop_limits():
    text = _text()
    assert re.search(r"one classifying rerun", text, re.I)
    assert re.search(r"\b3 per selection\b", text) and re.search(r"\b12 per ticket\b", text)


def test_o44_it_records_the_flaky_quarantine_numbers():
    text = _text()
    for needle in ("8 tests", "7 days", "48 h", "100 consecutive"):
        assert needle in text, needle


def test_o44_it_records_the_regime_decisions_by_name():
    text = _text().lower()
    for needle in (
        "tiers: none",
        "protected surface",
        "protected paths",
        "warrant",
        "repo-lint",
        "job object",
        "process group",
        "adapter",
        "acceptance",
    ):
        assert needle in text, needle


def test_o44_it_says_what_it_rejected():
    assert len(re.findall(r"Rejected:", _text())) >= 3
