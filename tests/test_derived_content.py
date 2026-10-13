"""Derived files reach merge-task.sh from the config, in owner mode and in workflow mode.

Content tests: the payload's prose is the product, so these read it.
"""
from __future__ import annotations

CONFIG = "claude/workflow/config.example.md"
SKILL = "claude/skills/batch-implement/SKILL.md"
WORKFLOW = "claude/workflows/pad-task.js"
PLANNER = "claude/agents/task-planner.md"


def test_config_commands_table_has_a_derived_files_row(payload_text):
    text = payload_text(CONFIG)
    assert "| Derived files |" in text
    assert "uv.lock: uv lock" in text


def test_config_says_a_rebuilt_lockfile_is_checked(payload_text):
    assert "uv lock --check" in payload_text(CONFIG)


def test_owner_mode_merge_passes_each_derived_file(payload_text):
    assert '--derived "<path>=<cmd>"' in payload_text(SKILL)


def test_workflow_mode_merge_passes_each_derived_file(payload_text):
    text = payload_text(WORKFLOW)
    assert "commands.derived" in text
    assert "--derived" in text


def test_planner_gives_a_hotspot_one_owner_per_wave(payload_text):
    text = payload_text(PLANNER)
    assert "HOTSPOTS" in text
    assert "one owner per wave" in text


def test_code_writer_checks_it_is_in_its_own_worktree_before_committing(payload_text):
    text = payload_text("claude/agents/code-writer.md")
    assert "**Check where you are**" in text
    assert "`git rev-parse --show-toplevel`" in text
    assert "worktree lost:" in text
