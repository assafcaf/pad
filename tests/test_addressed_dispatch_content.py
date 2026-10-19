"""Every dispatch has a fixed name and leaves an address, and the two are shown together.

The name (`E2-T2-owner`) says what an agent is; `SendMessage` reaches it by the id its dispatch
returned, so an id nobody wrote down is an agent nobody else can talk to. The rule binds both dispatchers, the orchestrator and the owner.

Content tests: the payload's prose is the product, so these read it.
"""
from __future__ import annotations

RULE = "claude/workflow/rules/addressed-dispatch.md"
SKILL = "claude/skills/pad-run/SKILL.md"
BRIEF = "claude/workflow/brief-template.md"
OWNER = "claude/agents/owner.md"
TEST_DESIGNER = "claude/agents/test-designer.md"


def test_the_rule_binds_both_dispatchers(payload_text):
    head = payload_text(RULE).split("---")[1]
    assert "kind: practice" in head
    assert "applies-to: orchestrator, owner" in head


def test_the_rule_says_where_each_id_is_written(payload_text):
    text = " ".join(payload_text(RULE).split())
    assert "brief's ownership map" in text
    assert 'channel.sh post <run id> <KEY> "<KEY>-tests <agent id>"' in text
    assert "When you tell the operator what you dispatched, name each agent with its id" in text


def test_an_owner_rereads_a_blank_owner_cell(payload_text):
    text = " ".join(payload_text(OWNER).split())
    assert "An Owner cell still blank when you need it: read the brief again" in text


def test_a_test_designer_knows_its_owners_address(payload_text):
    text = " ".join(payload_text(TEST_DESIGNER).split())
    assert "Your owner's address is the Owner cell of your ticket's row" in text


def test_every_agent_type_has_one_fixed_name(payload_text):
    text = payload_text(RULE)
    for row in ("| `owner` | `<KEY>-owner` |", "| `test-designer` | `<KEY>-tests` |",
                "| `evaluator` | `<KEY>-eval` |", "| `memory-curator` | `<epic key>-memory` |",
                "| `tracker` | `<epic key>-tracker`", "| `knowledge-scanner` | `scan-<area>` |"):
        assert row in text
    assert "A re-dispatch for the same ticket and type reuses the name" in " ".join(text.split())


def test_name_and_id_are_shown_together(payload_text):
    assert "show its name and id together" in " ".join(payload_text(SKILL).split())
    assert "| <KEY>-owner <agent id, filled at dispatch> |" in payload_text(BRIEF)


def test_scanners_and_the_tracker_are_named(payload_text):
    assert "named `scan-<area>`" in payload_text("claude/skills/knowledge-layer/SKILL.md")
    assert "named `scan-root`" in payload_text("claude/skills/setup-workflow/SKILL.md")
    assert "Dispatch it as `<epic key>-tracker`" in payload_text("claude/skills/tickets/SKILL.md")
