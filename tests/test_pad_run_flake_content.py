"""E2-T16 (O29): a flaky test becomes a fix ticket, never a rerun. Content tests."""
from __future__ import annotations

import re

SKILL = "claude/skills/pad-run/SKILL.md"
TESTING = "claude/workflow/testing.md"


def rows(text: str) -> list[str]:
    return [l for l in text.splitlines() if l.lstrip().startswith("|")]


def flake_row(text: str) -> str:
    hits = [r for r in rows(text) if re.search(r"flaky <test>", r) and "FLAKE <test>" in r]
    assert len(hits) == 1, "no single reports row for `flaky <test>` / `FLAKE <test>`"
    return hits[0]


def test_o29_no_row_reruns_a_merge_whose_failures_sit_outside_the_ticket(payload_text):
    for r in rows(payload_text(SKILL)):
        if "flaky <test>" not in r and re.search(r"didn't touch|outside the ticket", r, re.I):
            assert not re.search(r"re-?run|once more|again", r, re.I), r


def test_o29_flaky_test_line_writes_one_fix_ticket_through_the_lint_without_asking(payload_text):
    row = flake_row(payload_text(SKILL))
    assert re.search(r"one\b.*reproduction", row, re.I), row
    assert "/tickets" in row and "plan-check.sh" in row, row
    assert re.search(r"Ruling:", row), row
    assert re.search(r"without (waiting|asking)|never ask", row, re.I), row


def test_o29_dynamic_switches_to_single_until_the_fix_merges(payload_text):
    row = flake_row(payload_text(SKILL))
    assert re.search(r"dynamic", row) and re.search(r"single", row), row
    assert re.search(r"until (that|the) fix (merges|lands)", row, re.I), row


def test_o29_testing_guide_stops_the_whole_process_tree(payload_text):
    text = payload_text(TESTING)
    m = re.search(r"Pass under load.*?(?=\n\n##|\Z)", text, re.S)
    assert m
    assert re.search(r"process tree", m.group(0), re.I)


# ported-from: tests/test_owner_merge_content.py::test_o13_false_positive_rejection_is_resubmitted_and_costs_the_owner_nothing
def test_o29_no_false_positive_resubmit_is_left_in_the_skill(payload_text):
    text = payload_text(SKILL)
    assert not re.search(r"owner hears only the rerun", text, re.I)
    assert not re.search(r"false positive", text, re.I)
