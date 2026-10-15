"""O33: every capability names its surface and has one surface outcome, owned by one task.

Content tests: the skill and planner prose are the product.
"""
from __future__ import annotations

import re

SPEC = "claude/skills/spec/SKILL.md"
TICKETS = "claude/skills/tickets/SKILL.md"


def bullet(text: str, lead: str) -> str:
    m = re.search(rf"^- \*\*{re.escape(lead)}.*?(?=^- \*\*|^## |\Z)", text, re.S | re.M)
    assert m, f"no bullet starting {lead!r}"
    return m.group(0)


def test_o33_spec_outcome_level_can_be_a_named_surface(payload_text):
    assert "level: surface <name>" in payload_text(SPEC)


def test_o33_spec_template_outcome_line_lists_the_surface_level(payload_text):
    text = payload_text(SPEC)
    line = next(l for l in text.splitlines() if l.startswith("- [O1]"))
    assert "surface <name>" in line


def test_o33_spec_says_each_capability_names_its_surface(payload_text):
    text = payload_text(SPEC).lower()
    assert "capability" in text
    assert "## surfaces" in text  # points at the config section that names surfaces


def test_o33_spec_requires_one_surface_outcome_per_capability(payload_text):
    paras = [p for p in re.split(r"\n\s*\n", payload_text(SPEC)) if p.strip()]
    hits = [p.lower() for p in paras
            if "capabilit" in p.lower() and "surface outcome" in p.lower()]
    assert hits, "no paragraph ties each capability to a surface outcome"
    assert any("one surface outcome" in p or "exactly one" in p for p in hits)


def test_o33_spec_checklist_fails_a_capability_without_a_surface_outcome(payload_text):
    text = payload_text(SPEC)
    m = re.search(r"Check it before showing it:\n(.*?)\n\n", text, re.S)
    assert m, "no pre-show checklist"
    assert "surface" in m.group(1).lower()


def test_o33_tickets_cover_every_outcome_gives_surface_outcome_one_owner(payload_text):
    b = bullet(payload_text(TICKETS), "Outcomes only where tests are the reference").lower()
    assert "surface outcome" in b
    assert "exactly one ticket" in b


def test_o33_tickets_unowned_surface_outcome_is_a_gap_that_blocks_the_plan(payload_text):
    b = bullet(payload_text(TICKETS), "Outcomes only where tests are the reference")
    assert "GAP" in b
    assert "blocks the plan" in b.lower() or "block the plan" in b.lower()



