"""O24: each tier runs only the gates it needs.

Content tests: the agents' prose and the config's Commands table are the product, so these read
them. The designer runs named tests and typecheck; the owner runs named tests, typecheck and
lint, in every tier. No agent runs the full suite: merge-task.sh's gate does,
once per merge (KAN-107: agents' parallel full-suite runs pushed gates past 36 minutes).
"""
from __future__ import annotations

import re

DESIGNER = "claude/agents/test-designer.md"
OWNER = "claude/agents/owner.md"
CONFIG = "claude/workflow/config.example.md"


def numbered_step(text: str, number: int) -> str:
    """The text of procedure step `number` (from 'N. **' to the next numbered step or heading)."""
    m = re.search(rf"^{number}\. \*\*.*?(?=^\d+\. \*\*|^## )", text, re.S | re.M)
    assert m, f"no step {number}"
    return m.group(0)


def test_o24_designer_step_runs_typecheck_with_the_named_tests(payload_text):
    step = numbered_step(payload_text(DESIGNER), 5).lower()
    assert "typecheck" in step
    assert "named tests" in step


def test_o24_designer_leaves_the_full_suite_to_the_merge_gate_in_every_tier(payload_text):
    step = numbered_step(payload_text(DESIGNER), 5).lower()
    assert "never run the full suite" in step
    assert "merge gate" in step
    assert "complex" not in step


def test_o24_designer_report_has_no_full_suite_line(payload_text):
    assert "SUITE: <full suite command>" not in payload_text(DESIGNER)


def owner_build_step(text: str) -> str:
    step = numbered_step(text, 3)
    assert step.startswith("3. **Build**"), "owner step 3 is no longer Build"
    return " ".join(step.split()).lower()


def test_o24_owner_build_step_names_named_tests_typecheck_and_lint(payload_text):
    step = owner_build_step(payload_text(OWNER))
    assert "run the named tests, then the typecheck, then lint" in step


def test_o24_owner_never_runs_the_full_suite_in_any_tier(payload_text):
    step = owner_build_step(payload_text(OWNER))
    assert "never run the full suite" in step
    assert "merge gate runs it once" in step
    assert "complex" not in step


def test_o24_owner_report_names_no_full_suite_result(payload_text):
    text = payload_text(OWNER)
    assert "<full suite command> -> <result>" not in text
    assert "GREEN:" not in text


def test_o24_testing_guide_red_green_does_not_run_the_full_suite(payload_text):
    text = payload_text("claude/workflow/testing.md")
    assert "Run them, then the full suite." not in text
    assert "merge gate runs the full suite" in text


def test_o24_config_commands_table_has_a_typecheck_row(payload_text):
    assert re.search(r"^\| Typecheck \|", payload_text(CONFIG), re.M)


def test_o24_config_commands_table_has_dependency_directory_and_lockfile_rows(payload_text):
    text = payload_text(CONFIG)
    assert re.search(r"^\| Dependency directory \|", text, re.M)
    assert re.search(r"^\| Lockfile \|", text, re.M)
