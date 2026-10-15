"""E1-T16: the owner runs task-submit before it reports READY; the orchestrator no longer checks shas."""
from __future__ import annotations

import re

OWNER = "claude/agents/owner.md"
SKILL = "claude/skills/batch-implement/SKILL.md"


def steps(text: str) -> dict[int, str]:
    m = re.search(r"^## Procedure\s*\n(.*?)(?=^## )", text, re.S | re.M)
    assert m, "no Procedure section in owner.md"
    parts = re.split(r"^(\d+)\. ", m.group(1), flags=re.M)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def step(text: str, title: str) -> tuple[int, str]:
    found = [(n, s) for n, s in steps(text).items() if s.startswith(f"**{title}")]
    assert len(found) == 1, f"no single owner step titled {title!r}"
    return found[0]


def test_owner_submit_check_runs_task_submit_with_shas_and_test_paths(payload_text):
    _, body = step(payload_text(OWNER), "Submit check.")
    assert "task-submit.sh <epic head> <RED> HEAD" in body
    assert "--test-paths" in body


def test_owner_fixes_a_submit_fail_before_it_reports(payload_text):
    _, body = step(payload_text(OWNER), "Submit check.")
    assert "On `SUBMIT FAIL`, fix it here and run it again" in " ".join(body.split())


def test_owner_reports_ready_only_after_task_submit_and_the_rebase(payload_text):
    text = payload_text(OWNER)
    submit, _ = step(text, "Submit check.")
    rebase, body = step(text, "Rebase onto the epic head.")
    report, last = step(text, "Report")
    assert submit < rebase < report
    assert report == max(steps(text))
    assert "READY <KEY> <HEAD> <RED>" in last
    flat = " ".join(body.split())
    assert "re-run the named tests, typecheck and lint, and the submit check" in flat


def test_orchestrator_has_no_check_every_sha_paragraph(payload_text):
    text = payload_text(SKILL)
    assert "Check every sha" not in text
    assert "cat-file -t" not in text


def test_orchestrator_has_no_pre_relay_review(payload_text):
    assert not re.search(r"pre-relay", payload_text(SKILL), re.I)
