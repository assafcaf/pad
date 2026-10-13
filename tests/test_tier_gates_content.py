"""O24: each tier runs only the gates it needs.

Content tests: the agents' prose and the config's Commands table are the product, so these read
them. small and standard: designer runs named tests and typecheck; code-writer runs named tests,
typecheck and lint, in every tier. No agent runs the full suite: merge-task.sh's gate does,
once per merge (KAN-107: agents' parallel full-suite runs pushed gates past 36 minutes).
"""
from __future__ import annotations

import re

DESIGNER = "claude/agents/test-designer.md"
WRITER = "claude/agents/code-writer.md"
CONFIG = "claude/workflow/config.example.md"


def numbered_step(text: str, number: int) -> str:
    """The text of procedure step `number` (from 'N. **' to the next numbered step or heading)."""
    m = re.search(rf"^{number}\. \*\*.*?(?=^\d+\. \*\*|^## )", text, re.S | re.M)
    assert m, f"no step {number}"
    return m.group(0)


def paragraphs_with(text: str, *needles: str) -> list[str]:
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    return [p for p in paras if all(n.lower() in p.lower() for n in needles)]


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


def test_o24_code_writer_gate_step_names_named_tests_typecheck_and_lint(payload_text):
    step = numbered_step(payload_text(WRITER), 4).lower()
    for needle in ("named tests", "typecheck", "lint"):
        assert needle in step, needle


def test_o24_code_writer_leaves_the_full_suite_to_the_merge_gate_in_every_tier(payload_text):
    step = numbered_step(payload_text(WRITER), 4).lower()
    assert "never run the full suite" in step
    assert "complex" not in step


def test_o24_code_writer_green_line_names_no_full_suite_result(payload_text):
    text = payload_text(WRITER)
    assert "<full suite command> -> <result>" not in text
    assert "GREEN: <named tests command> -> <result>; <typecheck command> -> <result>" in text


def test_o24_testing_guide_red_green_does_not_run_the_full_suite(payload_text):
    text = payload_text("claude/workflow/testing.md")
    assert "Run them, then the full suite." not in text
    assert "merge gate runs the full suite" in text


def test_o24_code_writer_effort_note_no_longer_runs_full_suite_for_every_tier(payload_text):
    text = payload_text(WRITER).replace("**", "")
    hits = paragraphs_with(text, "iterate on the named tests only")
    assert hits, "the iterate-on-named-tests paragraph is gone"
    assert all("never the full suite" in p.lower() for p in hits)


def test_o24_config_commands_table_has_a_typecheck_row(payload_text):
    assert re.search(r"^\| Typecheck \|", payload_text(CONFIG), re.M)


def test_o24_config_commands_table_has_dependency_directory_and_lockfile_rows(payload_text):
    text = payload_text(CONFIG)
    assert re.search(r"^\| Dependency directory \|", text, re.M)
    assert re.search(r"^\| Lockfile \|", text, re.M)
