"""PAD 0.4.0: a visual ticket is closed by an independent judge, never by its owner's eye.

Content tests for `agents/evaluator.md` and the owner's visual step: the prose is the product.
"""
from __future__ import annotations

import re

EVALUATOR = "claude/agents/evaluator.md"
OWNER = "claude/agents/owner.md"


def flat(text: str) -> str:
    return " ".join(text.split())


def frontmatter(text: str) -> dict[str, str]:
    block = text.split("---")[1]
    return dict(re.findall(r"^(\w[\w-]*):\s*(.*)$", block, re.M))


def section(text: str, heading: str) -> str:
    m = re.search(r"^## " + re.escape(heading) + r"[ \t]*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert m, f"no '## {heading}' section"
    return m.group(1)


# The evaluator


def test_evaluator_is_a_read_only_agent_with_bash(payload_text):
    front = frontmatter(payload_text(EVALUATOR))
    assert front["name"] == "evaluator"
    tools = {t.strip() for t in front["tools"].split(",")}
    assert tools == {"Read", "Grep", "Glob", "Bash"}
    assert "Agent" not in tools and "Edit" not in tools and "SendMessage" not in tools


def test_evaluator_uses_bash_only_for_render_check(payload_text):
    text = flat(payload_text(EVALUATOR))
    assert "Use `Bash` only to run `bash .claude/workflow/bin/render-check.sh`" in text
    assert "Nothing else." in text


def test_evaluator_judges_with_a_fresh_context_and_never_sees_the_owners_reasoning(payload_text):
    text = flat(payload_text(EVALUATOR))
    front = frontmatter(payload_text(EVALUATOR))
    assert "fresh context" in front["description"]
    assert "Never sees the owner's reasoning" in front["description"]
    assert "The owner that built it may not judge its own work" in text
    assert "You never saw how it was built, and you must not ask." in text


def test_evaluator_input_is_only_images_evidence_dir_and_outcome(payload_text):
    body = flat(section(payload_text(EVALUATOR), "Input"))
    assert "Your dispatch carries only:" in body
    for part in ("the reference image's path", "the rendered image's path",
                 "the evidence directory", "the ticket's Outcome line"):
        assert part in body, part


def test_evaluator_checklist_is_in_order(payload_text):
    body = section(payload_text(EVALUATOR), "Procedure")
    assert "against this checklist, in order" in flat(body)
    items = re.findall(r"^\s+\d+\. \*\*(\w[\w ]*):\*\*", body, re.M)
    assert items == ["Elements", "Order and grouping", "Spacing", "Colour", "Type", "Content"]


def test_evaluator_stops_on_a_missing_image(payload_text):
    body = flat(section(payload_text(EVALUATOR), "Procedure"))
    assert "If either is missing or empty, stop with `VERDICT error <what>`" in body


def test_evaluator_writes_verdict_md_in_the_evidence_dir(payload_text):
    body = flat(section(payload_text(EVALUATOR), "Procedure"))
    assert "Write `verdict.md` in the evidence directory with `Write`" in body
    assert "each naming the element, the checklist item" in body


def test_evaluator_reports_exactly_one_verdict_line(payload_text):
    body = section(payload_text(EVALUATOR), "Report")
    assert "Exactly one line" in body
    block = re.search(r"```\n(.*?)```", body, re.S).group(1)
    lines = [l for l in block.splitlines() if l.strip()]
    assert [l.split()[:2] for l in lines] == [
        ["VERDICT", "match"], ["VERDICT", "mismatch"], ["VERDICT", "error"],
    ]


# The owner's visual step


def visual_step(payload_text) -> str:
    text = flat(payload_text(OWNER))
    m = re.search(r"\*\*A visual reference\*\* is met when(.*?)4\. \*\*Dev tests", text)
    assert m, "owner has no visual reference step"
    return m.group(1)


def test_owner_renders_with_render_check_into_the_evidence_dir(payload_text):
    body = visual_step(payload_text)
    assert "bash .claude/workflow/bin/render-check.sh --surface <surface> --route <route>" in body
    assert "--out <run dir>/evidence/<KEY>/app.png" in body
    assert "`reference.png`" in body


def test_owner_renders_at_most_three_rounds(payload_text):
    assert "at most three rounds" in visual_step(payload_text)


def test_owner_dispatches_the_evaluator_with_only_images_evidence_and_outcome(payload_text):
    body = visual_step(payload_text)
    assert ("dispatch an `evaluator` as `<KEY>-eval` with only the two image paths, the "
            "evidence directory and the ticket's Outcome line") in body


def test_owners_own_eye_never_closes_a_visual_ticket(payload_text):
    body = visual_step(payload_text)
    assert "Your own eye never closes a visual ticket." in body
    assert "`VERDICT match` lets you go on" in body
    assert "`FAILED <KEY> visual mismatch: <verdict path>`" in body


def test_owner_marks_a_visual_red_with_its_reference(payload_text):
    text = flat(payload_text(OWNER))
    assert "`test(<KEY>): reference <crop path> [red]`" in text
    assert "the evaluator's verdict (step 3) is the check" in text


def test_pad_run_lists_the_evaluator_as_dispatched_by_the_owner(payload_text):
    row = [l for l in payload_text("claude/skills/pad-run/SKILL.md").splitlines()
           if l.startswith("| `evaluator` |")]
    assert row and row[0].rstrip().endswith("| Its owner |"), row
