"""gate=full|affected and the host's test-worker budget reach merge-task.sh.

Content tests: the payload's prose is the product, so these read it.
"""
from __future__ import annotations

CONFIG = "claude/workflow/config.example.md"
SKILL = "claude/skills/pad-run/SKILL.md"
TESTING = "claude/workflow/testing.md"


def test_config_has_a_gate_option_a_worker_budget_and_a_per_test_timeout(payload_text):
    text = payload_text(CONFIG)
    assert "- **Gate:** `full`" in text
    assert "`affected`" in text
    assert "- **Test workers:**" in text
    assert "{workers}" in text
    assert "pytest-timeout" in text


def test_skill_passes_gate_affected_and_workers_and_runs_the_full_suite_at_the_end(payload_text):
    text = payload_text(SKILL)
    assert "--gate full|affected" in text
    assert "Test workers" in text
    assert "`merge.sh` reads" in text
    assert "even under `gate=affected`" in text


def test_testing_guide_asks_for_order_independent_bounded_tests(payload_text):
    text = payload_text(TESTING)
    assert "timeout" in text.lower()
