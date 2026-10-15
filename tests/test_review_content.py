"""O34, retargeted for 0.4.0: /pad-run reviews every wave with the operator (step 3f).

The 0.3.0 "Review checkpoints" section and its fix-<slug> tasks are retired: review.sh builds
the packet, and feedback becomes new tickets through /tickets (step 3g).
"""
from __future__ import annotations

import re

SKILL = "claude/skills/pad-run/SKILL.md"


def step(payload_text, letter: str, title: str) -> str:
    text = payload_text(SKILL)
    m = re.search(r"^\*\*%s\. %s[.,]\*\*(.*?)(?=^\*\*[a-z]\. |^## )" % (letter, re.escape(title)),
                  text, re.M | re.S)
    assert m, f"no step {letter}. {title}"
    return m.group(1)


def review(payload_text) -> str:
    return step(payload_text, "f", "Review every wave")


def test_o34_review_uses_the_configured_review_cadence(payload_text):
    body = review(payload_text)
    assert "Cadence" in body
    assert "per-wave` (the default)" in " ".join(body.split())
    for option in ("after-first-wave", "per-wave", "end-only", "none"):
        assert option in body


def test_o34_packet_is_built_by_review_sh_and_announced_without_stopping(payload_text):
    raw = review(payload_text)
    assert "bash .claude/workflow/bin/review.sh --run <run id>" in raw
    assert "review-<n>.md" in raw
    body = raw.lower()
    for part in ("merged keys and shas", "render pairs", "unverified"):
        assert part in body, part
    assert "push notification" in body
    assert "packet" in body
    assert re.search(r"without stopping|does not stop|never stop|doesn't stop|not stop", body)


def test_o34_review_reads_the_channel_and_turns_binding_decisions_into_rulings(payload_text):
    body = " ".join(review(payload_text).split())
    assert "`channel.sh read <run id> --since <ts>`" in body
    assert "becomes a ruling in the brief" in body


def test_o34_feedback_becomes_new_tickets_through_tickets(payload_text):
    body = step(payload_text, "g", "Replan")
    assert re.search(r"free-text feedback", body)
    assert "**new tickets**" in body
    assert "/tickets" in body
    assert "fix-<slug>" not in payload_text(SKILL)


def test_o34_final_review_at_end_of_epic_remains(payload_text):
    text = payload_text(SKILL)
    finish = text[text.index("## 4. Finish the epic"):]
    assert "**Final review.**" in finish
    assert "/code-review <level>" in finish
