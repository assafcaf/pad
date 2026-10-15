"""Rules in the prose: weakened-tests.sh passes a removal only when a rule explains it,
merge-task.sh records it, and no text tells an agent the check can be switched off or that a
rule-backed deletion is impossible.

Content tests: the payload's prose is the product, so these read it.
"""
from __future__ import annotations

SKILL = "claude/skills/pad-run/SKILL.md"
OWNER = "claude/agents/owner.md"
DOD = "claude/workflow/definition-of-done.md"
SETTINGS = "claude/settings.example.json"
MERGE_TASK = "claude/workflow/bin/merge-task.sh"


def test_owner_sends_test_removals_through_the_rules(payload_text):
    text = payload_text(OWNER)
    assert "**Test removals go through the rules.**" in text
    assert "rules.sh for owner" in text
    assert "a removal no rule explains is a `NEEDS_RULING`" in text


def test_owner_never_switches_the_check_off(payload_text):
    text = " ".join(payload_text(OWNER).split())
    assert "Never switch the check off or ask for it to be switched off" in text


def test_the_owner_report_has_no_removals_block(payload_text):
    text = payload_text(OWNER)
    assert "REMOVALS:" not in text
    assert "<file>::<test> | <rule> | <reason>" not in text


def test_the_orchestrator_does_not_review_removal_claims(payload_text):
    text = payload_text(SKILL)
    assert "weakened-tests.sh --claims" not in text
    assert "MISMATCH" not in text
    assert "REMOVALS reviewed:" not in text
    assert "you don't review its test removals" in " ".join(text.split())


def test_merge_task_records_each_rule_explained_removal(payload_text):
    assert 'echo "REMOVALS $key: $removals"' in payload_text(MERGE_TASK)


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
