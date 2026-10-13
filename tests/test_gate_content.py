"""gate=full|affected and the host's test-worker budget reach merge-task.sh in both modes.

Content tests: the payload's prose is the product, so these read it.
"""
from __future__ import annotations

CONFIG = "claude/workflow/config.example.md"
SKILL = "claude/skills/batch-implement/SKILL.md"
WORKFLOW = "claude/workflows/pad-task.js"
TESTING = "claude/workflow/testing.md"


def test_config_has_a_gate_option_defaulting_to_full(payload_text):
    text = payload_text(CONFIG)
    assert "- **Gate:** `full`" in text
    assert "`affected`" in text


def test_config_has_a_test_worker_budget(payload_text):
    text = payload_text(CONFIG)
    assert "- **Test workers:**" in text
    assert "{workers}" in text


def test_config_recommends_a_per_test_timeout(payload_text):
    assert "pytest-timeout" in payload_text(CONFIG)


def test_skill_takes_a_gate_option_and_passes_affected_and_workers(payload_text):
    text = payload_text(SKILL)
    assert "--gate full|affected" in text
    assert '--affected "<named tests>"' in text
    assert "--workers <n>" in text


def test_skill_runs_the_full_suite_at_the_epic_end_even_with_gate_affected(payload_text):
    assert "even under `gate=affected`" in payload_text(SKILL)


def test_workflow_mode_passes_affected_and_workers(payload_text):
    text = payload_text(WORKFLOW)
    assert "--affected" in text and "--workers" in text
    assert "args.gate" in text


def test_testing_guide_asks_for_order_independent_bounded_tests(payload_text):
    text = payload_text(TESTING)
    assert "timeout" in text.lower()
