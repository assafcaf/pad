"""Tickets are ownership units: the four tests, references, protected paths, and plan-check.sh.

Content tests: the payload's prose is the product, so these read it.
"""
from __future__ import annotations

import re

TEMPLATE = "claude/workflow/ticket-template.md"
TICKETS = "claude/skills/tickets/SKILL.md"
CONFIG = "claude/workflow/config.example.md"
SKILL = "claude/skills/pad-run/SKILL.md"


def _headings(text: str) -> list[str]:
    block = text.split("```markdown", 1)[1].split("```", 1)[0]
    return re.findall(r"^## (.+)$", block, re.M)


def test_template_has_the_ownership_headings_in_order_and_no_tier_files_or_interfaces(payload_text):
    assert _headings(payload_text(TEMPLATE)) == [
        "Outcome", "Reference", "Owns", "Touches", "Protected", "Depends on", "Out of scope", "Spec",
    ]
    text = payload_text(TEMPLATE)
    for gone in ("## Tier", "## Files", "## Interfaces", "Tiers", "at most 3 outcomes"):
        assert gone not in text, gone


def test_template_states_the_four_tests_and_spikes(payload_text):
    text = payload_text(TEMPLATE)
    for name in ("**Ownable.**", "**Checkable.**", "**Finishable by one owner**", "**One owner, start to merged.**"):
        assert name in text, name
    assert "**spike**" in text
    assert "never product code" in text
    assert "transverse sweep" in text


def test_tickets_split_by_surface_never_by_concern(payload_text):
    text = payload_text(TICKETS)
    assert "Split by surface or module, never by concern" in text
    assert "Two tickets\n  whose `Owns` overlap is a planning error" in text


def test_tickets_drop_the_old_model(payload_text):
    text = payload_text(TICKETS)
    for gone in ("Pin interfaces", "Implementers see only", "at most 3 outcomes", "Assign a tier",
                 "Sharing a file is **not** a blocking edge"):
        assert gone not in text, gone


def test_tickets_lint_with_plan_check_before_the_approval_table(payload_text):
    text = payload_text(TICKETS)
    lint = text.index("plan-check.sh .work/plans/<slug>.md")
    table = text.index("| Wave | Ticket | Reference | Owns | Touches | Protected | Depends on | Tags |")
    assert lint < table
    assert "`OVERLAPS`" in text and "`PROTECTED`" in text


def test_tickets_copy_the_scope_into_the_run(payload_text):
    assert ".work/runs/<epic key>/scope.md" in payload_text(TICKETS)


def test_config_has_protected_paths_and_no_tiers(payload_text):
    text = payload_text(CONFIG)
    assert "\n## Protected paths\n" in text
    assert "### Tiers" not in text
    assert "`task-planner`" not in text


def test_orchestrator_runs_plan_check_not_a_planner(payload_text):
    text = payload_text(SKILL)
    assert "plan-check.sh" in text
    assert "task-planner" not in text
    assert '--protected "<the config\'s Protected paths>" --ticket <ticket file>' in text
