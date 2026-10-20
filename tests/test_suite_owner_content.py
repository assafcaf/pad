"""O31, O50: the suite-owner agent's prompt: what it reads first, how it reports, what it runs.

Content tests: the agent's prose is the product.
"""
from __future__ import annotations

import re

AGENT = "claude/agents/suite-owner.md"
CONFIG = "claude/workflow/config.example.md"


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", ""))


def frontmatter(text: str) -> str:
    return text.split("---", 2)[1]


def test_suite_owner_is_an_agent_with_the_rules_preamble(payload_text):
    text = payload_text(AGENT)
    assert "name: suite-owner" in frontmatter(text)
    assert "rules.sh for suite-owner" in text


def test_o50_it_reads_suite_design_before_the_brief_and_the_packet(payload_text):
    text = flat(payload_text(AGENT))
    design = text.index("suite-design.md")
    assert design < text.index("brief")
    assert design < text.index("packet")


def test_o50_each_verdict_reason_cites_a_section_of_suite_design(payload_text):
    text = flat(payload_text(AGENT))
    assert "§<n>" in text
    assert "VERDICT <KEY> <id> promote|rewrite|retire <tier> — " in text


def test_o31_one_verdict_line_per_acceptance_test_in_the_report(payload_text):
    text = flat(payload_text(AGENT))
    assert "VERDICT <KEY> <id> promote|rewrite|retire <tier>" in text
    assert "exactly one" in text
    assert "submit-acceptance.sh verdicts" in text


def test_o31_it_runs_fast_and_heavy_before_landing(payload_text):
    text = flat(payload_text(AGENT))
    assert re.search(r"fast and heavy.{0,40}before (it )?land", text)


def test_suite_owner_runs_tests_only_through_pad_test(payload_text):
    text = flat(payload_text(AGENT))
    assert "pad-test.sh" in text
    assert "--role suite-owner" in text


def test_o33_it_keeps_the_flaky_quarantine_and_the_suite_map(payload_text):
    text = flat(payload_text(AGENT))
    assert "flaky.sh" in text
    assert "tests/MAP.md" in text or "Suite map" in text


def test_suite_owner_has_an_agents_row_in_the_config_example(payload_text):
    rows = [ln for ln in payload_text(CONFIG).splitlines() if ln.startswith("|") and "`suite-owner`" in ln]
    assert len(rows) == 1
