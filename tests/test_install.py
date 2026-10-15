"""install.sh ships the agents, the scripts, and the PAD version."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import BASH, BIN, PAYLOAD, ROOT, git


def _install(project: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [BASH, (ROOT / "install.sh").as_posix(), "--project", project.as_posix(),
         "--tracker", "local"],
        cwd=str(project), capture_output=True, text=True, encoding="utf-8",
        check=False, timeout=120,
    )


def _not_executable(paths: list[Path]) -> list[str]:
    """The names among paths that bash does not see as executable, in one bash run."""
    quoted = " ".join(f'"{p.as_posix()}"' for p in paths)
    r = subprocess.run(
        [BASH, "-c", f'for f in {quoted}; do test -x "$f" || basename "$f"; done'],
        capture_output=True, text=True, check=False,
    )
    return r.stdout.split()


def test_install_ships_agents_scripts_skills_and_the_pad_version(repo):
    """One install, checked for each thing it must ship."""
    assert _install(repo).returncode == 0

    # the owner agent, and no retired one
    agents = repo / ".claude" / "agents"
    assert (agents / "owner.md").read_text(encoding="utf-8") == (
        PAYLOAD / "claude" / "agents" / "owner.md"
    ).read_text(encoding="utf-8")
    for retired in ("ticket-owner", "code-writer", "epic-merger", "gate-runner"):
        assert not (agents / f"{retired}.md").exists()
    assert not (repo / ".claude" / "workflows").exists()

    # every script, executable
    scripts = sorted(p.name for p in BIN.glob("*.sh"))
    assert scripts
    installed = [repo / ".claude" / "workflow" / "bin" / name for name in scripts]
    for path in installed:
        assert path.is_file(), path.name
    assert _not_executable(installed) == []

    # the VERSION file, and the version written into config.md
    version_file = repo / ".claude" / "workflow" / "VERSION"
    version = (PAYLOAD / "claude" / "workflow" / "VERSION").read_text(encoding="utf-8").strip()
    assert version
    assert version_file.is_file()
    assert version_file.read_text(encoding="utf-8").strip() == version
    config = (repo / ".claude" / "workflow" / "config.md").read_text(encoding="utf-8")
    assert f"PAD version: {version}" in config.splitlines()
    assert "<PAD_VERSION>" not in config

    # the pad-update skill
    assert (repo / ".claude" / "skills" / "pad-update" / "SKILL.md").is_file()


@pytest.mark.slow
def test_install_ships_the_config_example_even_when_a_config_exists(repo):
    """/setup-workflow upgrade adds missing sections from `.claude/workflow/config.example.md`,
    so the template is installed and refreshed; only config.md itself is the project's."""
    config = repo / ".claude" / "workflow" / "config.md"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("# Workflow config\n\nmine\n", encoding="utf-8")
    assert _install(repo).returncode == 0
    example = repo / ".claude" / "workflow" / "config.example.md"
    assert example.is_file()
    assert example.read_text(encoding="utf-8") == (
        PAYLOAD / "claude" / "workflow" / "config.example.md"
    ).read_text(encoding="utf-8")
    assert config.read_text(encoding="utf-8") == "# Workflow config\n\nmine\n"


def _packaged_copy(dest: Path) -> Path:
    """A copy of install.sh and the payload outside any git checkout, as npx unpacks it."""
    dest.mkdir()
    shutil.copy(ROOT / "install.sh", dest / "install.sh")
    shutil.copytree(PAYLOAD, dest / "payload")
    return dest


def _install_from(source: Path, project: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [BASH, (source / "install.sh").as_posix(), "--project", project.as_posix(),
         "--tracker", "local"],
        cwd=str(project), capture_output=True, text=True, encoding="utf-8",
        check=False, timeout=120,
    )


@pytest.mark.slow
def test_install_from_a_git_checkout_records_its_commit_in_the_lock(repo, tmp_path):
    """/pad-update merges from the commit in `.claude/workflow/pad.lock`."""
    source = _packaged_copy(tmp_path / "pad-checkout")
    (source / "payload" / "migrations" / "0001-first.md").write_text("# 0001\n", encoding="utf-8")
    git("init", "-q", cwd=source)
    git("config", "user.name", "PAD Test", cwd=source)
    git("config", "user.email", "pad-test@example.invalid", cwd=source)
    git("config", "commit.gpgsign", "false", cwd=source)
    git("config", "core.autocrlf", "false", cwd=source)
    git("remote", "add", "origin", "https://example.invalid/pad", cwd=source)
    git("add", "-A", cwd=source)
    git("commit", "-q", "-m", "pad", cwd=source)
    commit = git("rev-parse", "HEAD", cwd=source)

    assert _install_from(source, repo).returncode == 0
    lock = (repo / ".claude" / "workflow" / "pad.lock").read_text(encoding="utf-8").splitlines()
    version = (PAYLOAD / "claude" / "workflow" / "VERSION").read_text(encoding="utf-8").strip()
    assert "source: https://example.invalid/pad" in lock
    assert f"commit: {commit}" in lock
    assert f"version: {version}" in lock
    notes = sorted(n.name[:4] for n in (source / "payload" / "migrations").glob("[0-9][0-9][0-9][0-9]-*.md"))
    assert f"migration: {notes[-1]}" in lock


@pytest.mark.slow
def test_install_from_a_packaged_copy_writes_no_lock_and_drops_a_stale_one(repo, tmp_path):
    """Without a commit the lock would name files it does not describe."""
    source = _packaged_copy(tmp_path / "pad-package")
    lock = repo / ".claude" / "workflow" / "pad.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("commit: 0123456\n", encoding="utf-8")
    assert _install_from(source, repo).returncode == 0
    assert not lock.exists()
