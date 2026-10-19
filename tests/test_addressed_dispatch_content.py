"""Every dispatch leaves an address: the returned agent id is written where peers read it.

`SendMessage` reaches an agent by the id its dispatch returned, so an id nobody wrote down is an
agent nobody else can talk to. The rule binds both dispatchers, the orchestrator and the owner.

Content tests: the payload's prose is the product, so these read it.
"""
from __future__ import annotations

RULE = "claude/workflow/rules/addressed-dispatch.md"
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
