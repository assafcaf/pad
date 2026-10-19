"""Baseline smoke test: the payload ships every skill and agent the installer copies.

E1-T1 builds the real harness (throwaway git repos driving payload scripts); this file only
keeps the suite non-empty and green so a run has a baseline to compare against.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD = ROOT / "payload" / "claude"

SKILLS = [
    "batch-implement", "knowledge-layer", "pad-run", "pad-update", "setup-workflow", "spec", "tickets",
]
AGENTS = [
    "evaluator",
    "knowledge-scanner",
    "memory-curator",
    "owner",
    "test-designer",
    "tracker",
]


def test_every_skill_has_a_skill_file():
    missing = [s for s in SKILLS if not (PAYLOAD / "skills" / s / "SKILL.md").is_file()]
    assert missing == []


def test_every_agent_has_an_agent_file():
    missing = [a for a in AGENTS if not (PAYLOAD / "agents" / f"{a}.md").is_file()]
    assert missing == []


def test_gate_scripts_are_present():
    for script in ["verify-red.sh", "weakened-tests.sh", "knowledge-paths.sh"]:
        assert (PAYLOAD / "workflow" / "bin" / script).is_file(), script


def test_knowledge_layer_can_be_run_by_an_agent():
    """/setup-workflow and /pad-run call it through the Skill tool, which the flag would block."""
    front = (PAYLOAD / "skills" / "knowledge-layer" / "SKILL.md").read_text(encoding="utf-8")
    front = front.split("---", 2)[1]
    assert "disable-model-invocation" not in front
    assert "/setup-workflow" in front and "/pad-run" in front
