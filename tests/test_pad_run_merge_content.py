"""E2-T3 (O17): /pad-run hands READY to merge.sh and owns the run's merge-strategy file.

Content tests: the skill's prose is the product, so these read it.
"""
from __future__ import annotations

import re

SKILL = "claude/skills/pad-run/SKILL.md"
DOD = "claude/workflow/definition-of-done.md"
TEMPLATE = "claude/workflow/brief-template.md"


def flat(text: str) -> str:
    return " ".join(text.split())


def paragraphs(text: str) -> list[str]:
    return [flat(p) for p in re.split(r"\n\s*\n", text) if p.strip()]


def mentioning(text: str, *patterns: str) -> list[str]:
    return [p for p in paragraphs(text) if all(re.search(x, p, re.I) for x in patterns)]


def test_o17_merge_flag_is_accepted_and_written_to_the_run_file_at_start(payload_text):
    text = payload_text(SKILL)
    assert "--merge <name> [opt=val" in text
    hits = mentioning(text, r"--merge", r"merge-strategy", r"start")
    assert hits, "skill never writes --merge to the run's merge-strategy file at start"
    assert any(".work/runs/<run id>/merge-strategy" in flat(text) for _ in hits)


# ported-from: tests/test_pad_run_merge_content.py::test_o17_ready_row_runs_merge_sh_in_the_background
def test_o17_ready_row_hands_merge_sh_to_a_ci_agent_in_the_foreground(payload_text):
    rows = [l for l in payload_text(SKILL).splitlines() if l.lstrip().startswith("| Owner `READY")]
    assert len(rows) == 1
    row = rows[0]
    assert "merge.sh --run <run id> --ready <KEY> <TASK_HEAD> <RED>" in row
    assert "<KEY>-ci" in row
    assert "run_in_background" not in row


def test_o17_each_result_line_is_acted_on(payload_text):
    text = flat(payload_text(SKILL))
    assert "MERGED|REJECTED|CONFLICT|ERROR <KEY>" in text
    assert "`QUEUED <KEY>`" in text


def test_o17_operator_strategy_change_is_a_ruling_that_rewrites_the_file(payload_text):
    hits = mentioning(payload_text(SKILL), r"operator", r"change", r"strategy", r"ruling", r"rewrite")
    assert hits, "no mid-run strategy change by the operator"
    assert any("merge-strategy" in h for h in hits), hits


def test_o17_dynamic_makes_the_orchestrator_write_the_file(payload_text):
    text = payload_text(SKILL)
    hits = mentioning(text, r"`dynamic`", r"`batch`", r"merge-strategies\.sh list", r"merge\.sh --run <run id> --status")
    assert hits, "the dynamic paragraph is missing"
    body = hits[0]
    assert "when to use" in body
    assert "STRATEGY <name> [opts] — <why>" in body
    assert "run-log.sh" in body
    assert re.search(r"never asks? the operator", body, re.I)
    assert re.search(r"never names? a strategy the list does not have", body, re.I)


def test_o17_a_fixed_strategy_is_never_rewritten_by_the_orchestrator(payload_text):
    hits = mentioning(payload_text(SKILL), r"fixed strategy|fixed name", r"never rewrites?")
    assert hits, "skill never says a fixed strategy is left alone"


def test_o17_orchestrator_never_builds_a_merge_task_command(payload_text):
    text = flat(payload_text(SKILL))
    assert re.search(r"never (puts together|builds?|assembles?) a `merge-task\.sh` command", text)
    assert "bash .claude/workflow/bin/merge-task.sh" not in text


def test_o17_gate_prose_says_the_gate_runs_on_the_tree_that_lands(payload_text):
    for rel in (DOD, TEMPLATE):
        text = flat(payload_text(rel))
        assert "once per merge" not in text, rel
        assert "on the tree that lands" in text, rel
