"""E4-T4 (C1, C4): the `ci` agent runs a merge in its own foreground and triages a red gate once.

Content tests: the agent's prose is the product.
"""
from __future__ import annotations

import re

CI = "claude/agents/ci.md"


def flat(text: str) -> str:
    return " ".join(text.split())


def frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert m, "ci.md has no frontmatter"
    return dict(l.split(":", 1) for l in m.group(1).splitlines() if ":" in l)


def test_c1_the_agent_is_named_ci_and_has_a_shell(payload_text):
    fm = frontmatter(payload_text(CI))
    assert fm["name"].strip() == "ci"
    assert "Bash" in fm["tools"]


def test_c1_it_runs_merge_sh_with_the_run_and_the_ready_line_in_its_foreground(payload_text):
    text = flat(payload_text(CI))
    assert "merge.sh --run <run id> --ready" in text
    assert "foreground" in text
    assert "run_in_background" not in text or re.search(r"(never|not|no)[^.]*run_in_background", text)


def test_c1_it_reports_the_scripts_last_line_unchanged(payload_text):
    text = flat(payload_text(CI))
    assert re.search(r"last line[^.]*unchanged|unchanged[^.]*last line", text), text


def test_c4_a_red_gate_runs_triage_sh_once(payload_text):
    text = flat(payload_text(CI))
    assert "triage.sh" in text
    assert re.search(r"\bonce\b", text)


def test_c4_it_reports_one_of_flaky_env_or_rejected_key(payload_text):
    text = flat(payload_text(CI))
    for verdict in ("`FLAKY`", "`ENV`", "`REJECTED <KEY>: "):
        assert verdict in text, verdict


def test_c4_it_never_edits_code_or_tests(payload_text):
    text = flat(payload_text(CI))
    assert re.search(r"never[^.]*edit[^.]*(code|tests)", text, re.I), text


def test_c4_it_has_no_file_editing_tool(payload_text):
    tools = {t.strip() for t in frontmatter(payload_text(CI))["tools"].split(",")}
    assert "Bash" in tools
    assert tools <= {"Read", "Grep", "Glob", "Bash"}, tools
