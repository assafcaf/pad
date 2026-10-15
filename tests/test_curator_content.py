"""E1-T13 O17: the curator routes halts and lessons into separate groups."""
from __future__ import annotations

import re

CURATOR = "claude/agents/memory-curator.md"
BATCH = "claude/skills/pad-run/SKILL.md"


def report_block(text: str) -> str:
    return text.split("## Report", 1)[1]


def test_o17_curator_reads_halts_md(payload_text):
    assert "HALTS.md" in payload_text(CURATOR)


def test_o17_report_has_local_candidates_field(payload_text):
    assert re.search(r"^LOCAL_CANDIDATES:", report_block(payload_text(CURATOR)), re.M)


def test_o17_report_has_repeated_rulings_field(payload_text):
    assert re.search(r"^REPEATED_RULINGS:", report_block(payload_text(CURATOR)), re.M)


def test_o17_curator_routes_by_halt_class(payload_text):
    body = payload_text(CURATOR)
    for cls in ("pad", "project", "machine"):
        assert f"`{cls}`" in body, cls
    assert "CLAUDE.local.md" in body


def test_o17_repeated_rulings_become_a_question_for_tickets(payload_text):
    body = payload_text(CURATOR)
    assert re.search(r"same reason", body) and "/tickets" in body


def test_o17_pr_body_lists_groups_separately(payload_text):
    step = payload_text(BATCH).split("**Push and open a draft PR**", 1)[1].split("**Report:**", 1)[0]
    for field in ("PROJECT_MD_CANDIDATES", "UPSTREAM_FIXES", "LOCAL_CANDIDATES", "REPEATED_RULINGS"):
        assert field in step, field


# --- 0.4.0: the curator reads the run's channel and knows the current agents ---

def test_curator_dispatch_carries_the_channel(payload_text):
    body = payload_text(CURATOR)
    dispatch = [p for p in body.split("\n\n") if p.startswith("Your dispatch carries")][0]
    assert "channel.md" in dispatch


def test_curator_routes_channel_posts_to_upstream_fixes(payload_text):
    section = payload_text(CURATOR).split("## Read the channel", 1)[1].split("\n## ", 1)[0]
    assert "UPSTREAM_FIXES" in section
    assert "PROJECT_MD_CANDIDATES" in section


def test_curator_names_the_current_memory_agents(payload_text):
    body = payload_text(CURATOR)
    for agent in ("`owner`", "`test-designer`", "`tracker`"):
        assert agent in body, agent


def test_curator_names_retired_agents_only_as_leftovers(payload_text):
    paras = payload_text(CURATOR).split("\n\n")
    for old in ("ticket-owner", "code-writer", "task-planner"):
        for p in paras:
            if old in p:
                assert "leftover" in p, p
