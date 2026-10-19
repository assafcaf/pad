"""E2-T4 O18: the /merge-strategy skill and its format file."""
from __future__ import annotations

import re

SKILL = "claude/skills/merge-strategy/SKILL.md"
FORMAT = "claude/skills/merge-strategy/STRATEGY-FORMAT.md"


def test_o18_skill_has_frontmatter_and_links_format(payload_text):
    text = payload_text(SKILL)
    assert text.startswith("---\n")
    assert re.search(r"^name: merge-strategy$", text, re.M)
    assert "STRATEGY-FORMAT.md" in text


def test_o18_maps_prose_to_grouping_gate_and_red(payload_text):
    text = payload_text(SKILL).lower()
    for word in ("grouping", "gate", "red"):
        assert word in text, word


def test_o18_asks_only_about_what_is_left_open(payload_text):
    text = payload_text(SKILL).lower()
    assert "only" in text and "left open" in text


def test_o18_refuses_three_contract_breaks_with_reasons(payload_text):
    text = payload_text(SKILL)
    assert "Refuse" in text
    assert "merge-task.sh" in text
    assert "submission check" in text
    assert "final gate" in text
    assert "saying why" in text.lower()


def test_o18_writes_pair_with_building_blocks_only(payload_text):
    text = payload_text(SKILL)
    assert "<name>.md" in text and "<name>.sh" in text
    for block in ("merge-candidate.sh", "merge-gate.sh", "merge-task.sh"):
        assert block in text, block


def test_o18_allow_rules_added_with_consent(payload_text):
    text = payload_text(SKILL)
    assert "allow rule" in text
    assert "consent" in text
    assert "settings" in text


def test_o18_when_to_use_in_orchestrator_signals(payload_text):
    text = payload_text(SKILL)
    assert "--status" in text
    assert "result line" in text
    assert "dynamic" in text


def test_o18_validates_then_rehearses_then_offers_default(payload_text):
    text = payload_text(SKILL)
    v = text.index("merge-strategies.sh validate")
    r = text.index("merge-strategies.sh rehearse")
    assert v < r
    assert "Merge strategy:" in text
    assert "default" in text


def test_o18_format_has_worked_example_gating_on_option_command(payload_text):
    text = payload_text(FORMAT)
    for key in ("name:", "script:", "description:", "options:"):
        assert key in text, key
    assert "PAD_OPT_" in text
    assert "merge-gate.sh" in text and "merge-candidate.sh" in text
    assert "merge-task.sh" in text and "--expect-tree" in text
    assert "dynamic" in text
