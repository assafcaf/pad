"""Derived files reach merge-task.sh from the config.

Content tests: the payload's prose is the product, so these read it.
"""
from __future__ import annotations

CONFIG = "claude/workflow/config.example.md"
SKILL = "claude/skills/pad-run/SKILL.md"


def test_config_has_a_derived_files_row_and_checks_a_rebuilt_lockfile(payload_text):
    text = payload_text(CONFIG)
    assert "| Derived files |" in text
    assert "uv.lock: uv lock" in text
    assert "uv lock --check" in text


def test_owner_mode_merge_passes_each_derived_file(payload_text):
    assert '--derived "<path>=<cmd>"' in payload_text(SKILL)


def test_plan_check_reports_hotspots_and_tickets_acts_on_them(payload_text):
    assert "HOTSPOTS" in payload_text("claude/workflow/bin/plan-check.sh")
    assert "HOTSPOTS" in payload_text("claude/skills/tickets/SKILL.md")


def test_owner_checks_it_is_in_its_own_worktree_before_committing(payload_text):
    text = payload_text("claude/agents/owner.md")
    assert "**Check where you are**" in text
    assert "`git rev-parse --show-toplevel`" in text
    assert "worktree lost:" in text
