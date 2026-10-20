"""/tickets, the ticket template and /spec say: one domain, one owner, end to end (O47)."""
from __future__ import annotations

import re

TEMPLATE = "claude/workflow/ticket-template.md"
TICKETS = "claude/skills/tickets/SKILL.md"
SPEC = "claude/skills/spec/SKILL.md"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def test_tickets_and_template_state_one_domain_one_owner_end_to_end(payload_text):
    for rel in (TICKETS, TEMPLATE):
        assert "one domain, one owner, end to end" in _norm(payload_text(rel)).lower(), rel


def test_no_time_based_size_rule_remains(payload_text):
    for rel in (TICKETS, TEMPLATE, SPEC):
        text = _norm(payload_text(rel))
        assert "45 minutes" not in text, rel
        assert "Size to one owner" not in text, rel


def test_template_has_domain_and_an_optional_split_section(payload_text):
    block = payload_text(TEMPLATE).split("```markdown", 1)[1].split("```", 1)[0]
    heads = re.findall(r"^## (.+)$", block, re.M)
    assert "Domain" in heads
    assert "Split" in heads
    assert heads.index("Domain") < heads.index("Owns")
    text = payload_text(TEMPLATE)
    for reason in ("independent-surface", "parallel-by-interface", "split-after-failures", "operator"):
        assert reason in text, reason


def test_tickets_approval_table_has_a_domain_column(payload_text):
    rows = [l for l in payload_text(TICKETS).splitlines() if l.startswith("| Wave")]
    assert rows and "Domain" in rows[0]


def test_tickets_skill_names_domain_lint_findings(payload_text):
    text = payload_text(TICKETS)
    assert "DOMAIN" in text
    assert "SPLIT" in text


def test_spec_domains_are_binding_and_name_what_each_owns(payload_text):
    text = payload_text(SPEC)
    section = text.split("## Domains", 1)[1].split("\n## ", 1)[0]
    assert "binding" in _norm(text).lower()
    assert "Owns" in section
