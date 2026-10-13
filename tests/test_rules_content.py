"""Rules in the prose: owners claim each removal, the orchestrator reviews the claims, and no
text tells an agent the weakened-tests gate can never be passed by a deletion.

Content tests: the payload's prose is the product, so these read it.
"""
from __future__ import annotations

SKILL = "claude/skills/batch-implement/SKILL.md"
OWNER = "claude/agents/ticket-owner.md"
DOD = "claude/workflow/definition-of-done.md"
SETTINGS = "claude/settings.example.json"


def test_the_ready_block_carries_a_removals_section(payload_text):
    text = payload_text(OWNER)
    assert "REMOVALS:" in text
    assert "<file>::<test> | <rule> | <reason>" in text


def test_the_orchestrator_checks_claims_before_it_merges(payload_text):
    text = payload_text(SKILL)
    assert "weakened-tests.sh --claims" in text
    assert "MISMATCH" in text


def test_an_unexplained_removal_or_mismatch_is_a_question_for_the_operator(payload_text):
    text = payload_text(SKILL)
    assert "unexplained removal or a `MISMATCH` is a question" in text


def test_the_pr_body_lists_each_removal_and_its_rule(payload_text):
    assert "**Test removals**" in payload_text(SKILL)


def test_no_agent_is_told_a_rule_backed_deletion_is_impossible(payload_text):
    for rel in (SKILL, OWNER):
        assert "Never override the weakened-tests gate" not in payload_text(rel)
    assert "Nothing switches the check off" in payload_text(SKILL)


def test_definition_of_done_names_the_rules(payload_text):
    assert "test-removal rule" in payload_text(DOD)


def test_settings_example_allows_agents_to_load_rules(payload_text):
    assert "Bash(bash .claude/workflow/bin/rules.sh *)" in payload_text(SETTINGS)


WORKFLOW = "claude/workflows/pad-task.js"


def test_workflow_mode_stops_for_review_when_a_branch_removes_tests(payload_text):
    text = payload_text(WORKFLOW)
    assert "weakened-tests.sh --claims /dev/null" in text
    assert "NEEDS_RULING ${key} removes tests" in text


def test_workflow_mode_resumes_a_removal_review_from_a_removals_ruling(payload_text):
    assert "REMOVALS reviewed:" in payload_text(SKILL)
    assert "/REMOVALS reviewed:/" in payload_text(WORKFLOW)
