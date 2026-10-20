"""E1-T11 (O13, O19): a ticket merges through merge-task.sh run by the orchestrator.

No revert of a revert, no merger agent to stall a merge, and neither a merge failure nor a
tracker FAIL stops the run. Content tests: the skill and agent prose is the product.
"""
from __future__ import annotations

import re

import pytest

from conftest import PAYLOAD

SKILL = "claude/skills/pad-run/SKILL.md"
OWNER = "claude/agents/owner.md"
RETIRED = (
    "claude/agents/ticket-owner.md",
    "claude/agents/code-writer.md",
    "claude/agents/epic-merger.md",
    "claude/agents/gate-runner.md",
    "claude/workflows/pad-task.js",
)


def blocks(text: str) -> list[str]:
    """Prose paragraphs and list items, with each table row as its own block."""
    out: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        if not para.strip():
            continue
        lines = para.strip().splitlines()
        if all(l.lstrip().startswith("|") for l in lines):
            out.extend(lines)
        else:
            out.extend(i for i in re.split(r"\n(?=\s*(?:[-*]|\d+\.)\s)", para) if i.strip())
    return out


def sentences(text: str) -> list[str]:
    return [s for b in blocks(text) for s in re.split(r"(?<=[.!?:])\s+(?=[A-Z`*])", b) if s.strip()]


def blocks_matching(text: str, *patterns: str) -> list[str]:
    return [b for b in blocks(text) if all(re.search(p, b, re.I) for p in patterns)]


def report_row(text: str, start: str) -> str:
    """The one row of the reports table whose first cell starts with `start`."""
    rows = [l for l in text.splitlines() if l.lstrip().startswith(f"| {start}")]
    assert len(rows) == 1, f"reports table has no single row starting {start!r}"
    return rows[0]


def operator_list(text: str) -> str:
    """From 'need the operator' to the end of its paragraph: the list of what needs a person."""
    m = re.search(r"need\s+the\s+operator.*?(?=\n\s*\n)", text, re.S)
    assert m, "skill no longer lists what needs the operator"
    return m.group(0)


# O13: no revert of a revert; false positives are resubmitted; reverts only for resources.

def test_o13_no_payload_file_mentions_remerge():
    offenders = [
        p.relative_to(PAYLOAD).as_posix()
        for p in PAYLOAD.rglob("*")
        if p.is_file() and "REMERGE" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert offenders == []


@pytest.mark.parametrize("rel", [SKILL, OWNER])
def test_o13_o19_no_revert_of_a_revert_and_no_retired_merger_replies(payload_text, rel):
    text = payload_text(rel)
    assert not re.search(r"revert sha|<revert", text, re.I)
    assert not re.search(r"false[- ]positive revert", text, re.I)
    assert "`REVERTED" not in text
    assert "SUBMITTED" not in text


# ported-from: tests/test_owner_merge_content.py::test_o13_every_revert_in_skill_and_owner_is_for_a_serial_resource
def test_o13_every_revert_in_skill_and_owner_is_for_a_serial_resource_or_a_triaged_heavy(payload_text):
    for rel in (SKILL, OWNER):
        stray = [
            b for b in blocks_matching(payload_text(rel), r"revert")
            if not re.search(r"resource|triage\.sh", b, re.I)
        ]
        assert stray == [], f"{rel}: revert outside a serial-resource failure or a triaged heavy: {stray}"


def test_o23_the_skill_no_longer_says_a_serial_resource_is_the_only_reason_to_revert(payload_text):
    text = " ".join(payload_text(SKILL).split())
    assert "only reason a merge is ever reverted" not in text


def test_o13_resource_failure_reverts_with_the_revert_merge_capability(payload_text):
    hits = blocks_matching(payload_text(SKILL), r"RESOURCE_PROBES", r"revert")
    assert hits, "skill never reverts a merge whose resource probe failed"
    assert any("the `revert-merge` move" in b for b in hits), hits
    assert "`REVERT " not in payload_text(SKILL)


def test_o13_retired_agents_and_workflow_are_gone():
    left = [rel for rel in RETIRED if (PAYLOAD / rel).exists()]
    assert left == [], left


# O19: the orchestrator runs merge-task.sh; a failure retries fresh; tracker FAIL never stops.

def test_o19_orchestrator_sends_conflict_or_rejected_to_the_owner_unchanged(payload_text):
    row = report_row(payload_text(SKILL), "`merge.sh` `CONFLICT")
    assert "REJECTED" in row
    assert re.search(r"SendMessage. the owner that line unchanged", row, re.I)


def test_o19_ready_row_reintroduces_no_sha_check(payload_text):
    row = report_row(payload_text(SKILL), "Owner `READY")
    assert not re.search(r"\bshas?\b", row, re.I), row


def test_o19_merge_error_is_retried_once_fresh_then_parked_as_a_question(payload_text):
    hits = blocks_matching(payload_text(SKILL), r"`ERROR|exit 2")
    assert hits, "skill never handles merge-task.sh's ERROR / exit 2"
    assert any(
        re.search(r"\bonce\b", b, re.I) and re.search(r"fresh", b, re.I) for b in hits
    ), hits
    assert any(re.search(r"question|park", b, re.I) for b in hits), hits


def test_o19_neither_a_merge_failure_nor_a_tracker_fail_needs_the_operator(payload_text):
    block = operator_list(payload_text(SKILL))
    assert not re.search(r"merger|merge-task|`ERROR", block, re.I), block
    assert not re.search(r"tracker", block, re.I), block


def test_o19_skill_dispatches_no_epic_merger_and_has_no_hold_protocol(payload_text):
    text = payload_text(SKILL)
    assert "`CONTINUE`" not in text
    assert not re.search(r"\bholding\b", text, re.I)
    assert not re.search(r"[Dd]ispatch `epic-merger`", text)
    assert not re.search(r"^\|\s*`epic-merger`", text, re.M)
    assert not re.search(r"\bthe merger\b", text, re.I)


def test_o19_owner_hands_over_to_the_orchestrator_not_a_merger(payload_text):
    text = payload_text(OWNER)
    assert not re.search(r"\bmerger\b", text, re.I)


def test_o19_tracker_fail_is_never_a_question_and_lets_the_run_carry_on(payload_text):
    text = payload_text(SKILL)
    hits = [x for x in sentences(text) if re.search(r"tracker", x) and "FAIL" in x]
    asking = [b for b in hits if re.search(r"question", b, re.I)]
    assert asking == [], asking
    hits = [x for x in sentences(text) if re.search(r"tracker|ledger", x, re.I) and "FAIL" in x]
    assert any(
        re.search(r"never stops?|keeps? going|carr(y|ies) on|continues?", b, re.I) for b in hits
    ), hits
