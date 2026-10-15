"""O27, O28: the owner builds only after red is proven; the designer proves its own red.

Content tests: the agents' prose is the product, so these read it. They assert only what O27 and
O28 need, not the git moves, which test_git_moves_content.py covers.
"""
from __future__ import annotations

import re

DESIGNER = "claude/agents/test-designer.md"
OWNER = "claude/agents/owner.md"


def flat(text: str) -> str:
    """Lowercased, markdown emphasis dropped, whitespace collapsed."""
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).lower()


def procedure_steps(text: str) -> dict[int, str]:
    m = re.search(r"^## Procedure\s*\n(.*?)(?=^## )", text, re.S | re.M)
    assert m, "no Procedure section"
    parts = re.split(r"^(\d+)\. ", m.group(1), flags=re.M)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


# --- O27: the owner builds only after red is proven ---

def test_o27_owner_has_no_prepared_or_peer_relay_lines(payload_text):
    text = payload_text(OWNER)
    assert "PREPARED" not in text
    assert "PEER <id>" not in text
    assert "PEER:" not in text
    assert "code-writer" not in text


def test_o27_owner_takes_and_proves_red_before_it_builds(payload_text):
    steps = procedure_steps(payload_text(OWNER))
    proof = min(n for n, s in steps.items() if "verify-red.sh" in s)
    build = min(n for n, s in steps.items() if flat(s).startswith("build"))
    assert proof < build
    assert "red ok" in flat(steps[proof])
    red = flat(steps[proof])
    assert "red_commit" in red and "take-red" in red


# --- O27: objections go straight to the test-designer ---

def test_o27_owner_sends_an_objection_to_the_designer_and_an_unresolved_one_to_a_ruling(payload_text):
    paras = [
        flat(p) for p in re.split(r"\n\s*\n", payload_text(OWNER)) if "looks wrong" in p
    ]
    assert paras, "owner.md says nothing about a test that looks wrong"
    para = paras[0]
    assert "sendmessage <key>-tests" in para
    assert "the test id and the ticket line it contradicts" in para
    assert '"hard to pass" is not an objection' in para
    assert any("can't agree" in p and "needs_ruling" in p for p in paras), paras


def test_o27_designer_answers_its_owners_objection_with_a_new_red_commit(payload_text):
    text = flat(payload_text(DESIGNER))
    assert "a test your owner says is wrong" in text
    assert "never amend or rewrite the red commit" in text
    assert "your owner starts a code-writer" not in text


# --- O28: designer proves its own red ---

def test_o28_designer_proves_its_own_red_as_its_last_step_after_the_commit(payload_text):
    steps = procedure_steps(payload_text(DESIGNER))
    last = steps[max(steps)]
    assert "verify-red.sh" in last
    assert "red commit" in flat(last)
    assert "red ok" in flat(last)
    assert "only after" in flat(last) or "until" in flat(last)
    commit = [n for n, s in steps.items() if "commit once" in flat(s)]
    assert commit and max(commit) < max(steps)
