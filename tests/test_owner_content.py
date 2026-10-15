"""The owner's contract: one owner per ticket, one report line, strict tickets get their tests
from a blocking test-designer, and peers talk to each other, never through the orchestrator.

Content tests: the agent's prose is the product, so these read it.
"""
from __future__ import annotations

import re

OWNER = "claude/agents/owner.md"
SKILL = "claude/skills/batch-implement/SKILL.md"


def flat(text: str) -> str:
    """Markdown emphasis and code ticks dropped, whitespace collapsed."""
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", ""))


def section(text: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert m, f"owner.md has no ## {heading} section"
    return m.group(1)


def fenced(text: str) -> list[str]:
    m = re.search(r"^```[^\n]*\n(.*?)^```", text, re.S | re.M)
    assert m, "no fenced block"
    return [line for line in m.group(1).splitlines() if line.strip()]


# --- one report line ---


def test_owner_report_is_exactly_one_of_three_lines(payload_text):
    report = section(payload_text(OWNER), "Report")
    assert "Exactly one line, then nothing" in report
    forms = [line.split()[0] for line in fenced(report)]
    assert forms == ["READY", "FAILED", "NEEDS_RULING"]


def test_owner_ready_line_carries_the_task_head_and_red_shas(payload_text):
    lines = fenced(section(payload_text(OWNER), "Report"))
    assert lines[0] == "READY <KEY> <TASK_HEAD sha> <RED sha>"


def test_owner_report_has_no_retired_block_fields(payload_text):
    text = payload_text(OWNER)
    for field in ("STATUS:", "SUBMITTED", "LEDGER_COMMENT", "DEV_TESTS:", "REMOVALS:"):
        assert field not in text, field


def test_skill_acts_on_the_owners_three_report_lines(payload_text):
    text = payload_text(SKILL)
    for row in ("| Owner `READY <KEY> <TASK_HEAD> <RED>`", "| Owner `NEEDS_RULING <KEY>",
                "| Owner `FAILED <KEY>"):
        assert row in text, row


# --- strict discipline: test-designer as a blocking child ---


def test_strict_tiers_get_a_test_designer_as_a_blocking_child(payload_text):
    strict = flat(section(payload_text(OWNER), "The strict discipline"))
    assert "tier is standard or complex" in strict
    assert "Dispatch a test-designer as <KEY>-tests, block on it, and take its red commit" in strict
    assert "the tests are read-only to you" in strict


def test_small_tickets_tests_are_the_owners_written_first(payload_text):
    strict = flat(section(payload_text(OWNER), "The strict discipline"))
    assert "A small ticket's tests are yours to write, first, before the code" in strict


def test_owner_never_edits_a_test_it_took(payload_text):
    rules = flat(section(payload_text(OWNER), "The tests are not yours (strict)"))
    assert "Never edit, skip, xfail, delete or rename a test you took" in rules
    assert "never weaken an assertion" in rules


# --- peers talk directly ---


def test_owner_talks_to_other_owners_directly(payload_text):
    text = flat(payload_text(OWNER))
    assert "agree an interface with them directly by SendMessage" in text
    assert "never route a peer question through the orchestrator" in text


def test_a_question_about_another_tickets_files_goes_to_its_owner(payload_text):
    rulings = flat(section(payload_text(OWNER), "Questions and rulings"))
    assert "One that changes another ticket's files or interface goes to that ticket's owner by message" in rulings
    assert "NEEDS_RULING <KEY> <question>" in rulings


def test_owner_resolves_a_rebase_conflict_in_a_peers_file_with_that_peer(payload_text):
    text = flat(payload_text(OWNER))
    assert "in a file another ticket owns, SendMessage its owner and agree the result first" in text


def test_owner_never_lands_its_own_branch(payload_text):
    text = flat(payload_text(OWNER))
    assert "Never push, merge into the epic branch" in text
