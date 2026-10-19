"""A fresh install ships the merge strategies; an update leaves a repo's own strategy alone.

Outcomes O21, O22, O32 of the merge-strategies epic.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from conftest import BASH, BIN, PAYLOAD, ROOT, git

CONFIG = "claude/workflow/config.example.md"
SETTINGS = "claude/settings.example.json"
MIGRATION = "migrations/0004-merge-strategy.md"
SETUP = "claude/skills/setup-workflow/SKILL.md"
NEW_SCRIPTS = ("merge", "merge-strategies", "merge-candidate", "merge-gate", "merge-ticket",
               "merge-rehearse", "merge-cancel", "suite-slot")


def _install(project: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [BASH, (ROOT / "install.sh").as_posix(), "--project", project.as_posix(),
         "--tracker", "local"],
        cwd=str(project), capture_output=True, text=True, encoding="utf-8",
        check=False, timeout=120,
    )


@pytest.fixture
def pad_update_project(tmp_path: Path, repo: Path):
    """A throwaway PAD clone that ships a strategy, a project that installed it, a runner."""
    clone = tmp_path / "pad"
    clone.mkdir()
    git("init", "-q", cwd=clone)
    git("symbolic-ref", "HEAD", "refs/heads/main", cwd=clone)
    for key, value in (("user.name", "PAD Test"), ("user.email", "pad-test@example.invalid"),
                       ("commit.gpgsign", "false"), ("core.autocrlf", "false")):
        git("config", key, value, cwd=clone)

    def commit(text: str) -> str:
        path = clone / "payload" / "claude" / "workflow" / "merge-strategies" / "single.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        version = clone / "payload" / "claude" / "workflow" / "VERSION"
        version.write_bytes(b"0.2.0\n")
        git("add", "-A", cwd=clone)
        git("commit", "-q", "-m", "c", cwd=clone)
        return git("rev-parse", "HEAD", cwd=clone)

    base = commit("one\n")
    shipped = repo / ".claude" / "workflow" / "merge-strategies" / "single.md"
    shipped.parent.mkdir(parents=True, exist_ok=True)
    shipped.write_bytes(b"one\n")
    lock = repo / ".claude" / "workflow" / "pad.lock"
    lock.write_bytes(
        f"source: https://example.invalid/pad\ncommit: {base}\nversion: 0.2.0\nmigration: 0000\n"
        .encode("utf-8"))
    commit("one\ntwo\n")

    def run() -> subprocess.CompletedProcess:
        script = BIN / "pad-update.sh"
        return subprocess.run(
            [BASH, script.as_posix(), "--pad", clone.as_posix(), "--project", repo.as_posix()],
            cwd=str(repo), capture_output=True, text=True, encoding="utf-8",
            check=False, timeout=120)

    return repo, run


def _execution(text: str) -> str:
    return text.split("\n## Execution", 1)[1]


def test_o21_install_ships_strategies_dynamic_default_allow_rules_and_the_skill(repo):
    assert _install(repo).returncode == 0
    claude = repo / ".claude"
    strategies = claude / "workflow" / "merge-strategies"
    for name in ("single.md", "single.sh", "batch.md", "batch.sh"):
        assert (strategies / name).is_file(), name
    assert (claude / "skills" / "merge-strategy" / "SKILL.md").is_file()

    config = (claude / "workflow" / "config.md").read_text(encoding="utf-8")
    assert "- **Merge strategy:** `dynamic`" in _execution(config)

    text = (PAYLOAD / CONFIG).read_text(encoding="utf-8")
    execution = _execution(text)
    assert "- **Merge strategy:** `dynamic`" in execution
    assert "merge-strategies/" in execution
    assert "fixed" in execution

    allow = json.loads((PAYLOAD / SETTINGS).read_text(encoding="utf-8"))["permissions"]["allow"]
    for script in NEW_SCRIPTS:
        assert f"Bash(bash .claude/workflow/bin/{script}.sh *)" in allow, script


def test_o21_config_example_gives_host_suite_slots_none(payload_text):
    execution = _execution(payload_text(CONFIG))
    assert re.search(r"^- \*\*Host suite slots:\*\* `none`", execution, re.M)
    assert "PAD_HOST_SLOTS_DIR" in execution


def test_o22_update_leaves_a_repos_own_strategy_untouched(pad_update_project):
    project, run = pad_update_project
    own = project / ".claude" / "workflow" / "merge-strategies" / "mine.md"
    own.parent.mkdir(parents=True, exist_ok=True)
    own.write_bytes(b"---\nname: mine\n---\nours\n")
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert own.read_bytes() == b"---\nname: mine\n---\nours\n"
    assert "mine.md" not in result.stdout


def test_o22_migration_0004_asks_for_the_choice_and_writes_the_line(payload_text):
    text = payload_text(MIGRATION)
    assert text.startswith("# 0004")
    for heading in ("Applies when:", "## Steps", "## Check"):
        assert heading in text
    for choice in ("`dynamic`", "`batch`", "`single`"):
        assert choice in text
    assert "Merge strategy:" in text
    assert "Host suite slots" in text


def test_o22_setup_workflow_names_the_merge_strategy_skill(payload_text):
    assert "/merge-strategy" in payload_text(SETUP)


def test_o32_gate_default_is_affected_and_the_final_full_gate_is_why(payload_text):
    execution = _execution(payload_text(CONFIG))
    assert "- **Gate:** `affected`" in execution
    assert "final full" in execution
    assert "safe" in execution
    batch = (PAYLOAD / "claude" / "workflow" / "merge-strategies" / "batch.sh").read_text(
        encoding="utf-8")
    assert "--gate" in batch and "affected" in batch
