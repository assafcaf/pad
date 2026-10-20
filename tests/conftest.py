"""Shared harness: throwaway git repos with linked worktrees, and a runner for payload scripts.

Everything here builds its own repos under pytest's tmp_path and reads only `payload/` from this
checkout, never the installed `.claude/`. It must behave the same under Git Bash on Windows and
bash on Linux, with git as old as 2.23 (no `git init -b`, no `--path-format`).

Tiers. On Windows every payload-script run costs seconds, so a script's long-tail tests are
marked `@pytest.mark.slow` and the default run (`addopts` in pyproject.toml) skips them: it is
the content tests plus at least one quick test per script. `pytest -m slow` runs only the rest;
`pytest -m ""` runs everything. `_TIER_HERE` below tiers the modules not yet marked by hand.
"""
from __future__ import annotations

import os
import shutil
import sys
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD = ROOT / "payload"
BIN = PAYLOAD / "claude" / "workflow" / "bin"


def _find_bash() -> str:
    """The bash that runs payload scripts. On Windows, prefer Git's own bash over WSL's."""
    override = os.environ.get("PAD_BASH")
    if override:
        return override
    if os.name == "nt":
        git = shutil.which("git")
        if git:
            for parent in Path(git).resolve().parents:
                candidate = parent / "bin" / "bash.exe"
                if candidate.is_file():
                    return str(candidate)
    bash = shutil.which("bash")
    if not bash:
        raise RuntimeError("bash is not available: install it or set PAD_BASH")
    return bash


BASH = _find_bash()

# Modules not yet tiered by hand: every test in them that builds a repo or runs a script is
# `slow`, except the named smoke tests. Move a module's marks into the file and drop it here.
_TIER_HERE = {
    "test_preflight.py": {"test_o39_a_missing_config_fails_with_a_count_and_exit_1"},
    "test_rehearse.py": {"test_o46_outside_a_git_repo_the_rehearsal_fails"},
    "test_pad_update.py": {
        "test_an_untouched_file_is_replaced_with_the_new_one",
        "test_a_directory_that_is_not_a_pad_clone_is_refused",
    },
    "test_upgrade_030.py": set(),
    "test_setup_content.py": set(),
}
_HEAVY_FIXTURES = {"run_script", "repo", "worktree", "pad"}


def pytest_collection_modifyitems(config, items):
    for item in items:
        smoke = _TIER_HERE.get(Path(str(item.fspath)).name)
        if smoke is None or item.get_closest_marker("slow"):
            continue
        if item.originalname not in smoke and _HEAVY_FIXTURES & set(item.fixturenames):
            item.add_marker(pytest.mark.slow)


def git(*args: str, cwd: Path) -> str:
    """Run git in cwd, fail loudly, and return stdout stripped."""
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}:\n{result.stderr}")
    return result.stdout.strip()


def _build_repo(tmp_path: Path) -> Path:
    """Build tmp_path/main (branch `main`, one commit) pushed to a bare tmp_path/origin.git."""
    origin = tmp_path / "origin.git"
    main = tmp_path / "main"
    origin.mkdir()
    main.mkdir()
    git("init", "--bare", "-q", cwd=origin)
    git("symbolic-ref", "HEAD", "refs/heads/main", cwd=origin)
    git("init", "-q", cwd=main)
    git("symbolic-ref", "HEAD", "refs/heads/main", cwd=main)
    git("config", "user.name", "PAD Test", cwd=main)
    git("config", "user.email", "pad-test@example.invalid", cwd=main)
    git("config", "commit.gpgsign", "false", cwd=main)
    git("config", "core.autocrlf", "false", cwd=main)
    (main / "README.md").write_text("fixture repo\n", encoding="utf-8")
    git("add", "README.md", cwd=main)
    git("commit", "-q", "-m", "initial", cwd=main)
    git("remote", "add", "origin", origin.as_posix(), cwd=main)
    git("push", "-q", "-u", "origin", "main", cwd=main)
    # Sample hooks are inert; dropping them makes every per-test copy cheaper.
    for hooks in (main / ".git" / "hooks", origin / "hooks"):
        for sample in hooks.glob("*.sample"):
            sample.unlink()
    return main


@pytest.fixture(scope="session")
def _repo_template(tmp_path_factory) -> Path:
    """One repo + origin per session (per xdist worker); each test gets a copy of it."""
    base = tmp_path_factory.mktemp("repo-template")
    _build_repo(base)
    return base


@pytest.fixture
def repo(tmp_path: Path, _repo_template: Path) -> Path:
    """A fresh git repo on branch `main` with one commit, pushed to a bare `origin`.

    It is a copy of a session template, laid out as before (tmp_path/main, tmp_path/origin.git),
    with `origin` repointed at this test's own bare copy. Nothing in it is shared between tests.
    """
    shutil.copytree(_repo_template / "origin.git", tmp_path / "origin.git")
    main = tmp_path / "main"
    shutil.copytree(_repo_template / "main", main)
    config = main / ".git" / "config"
    old = (_repo_template / "origin.git").as_posix().encode()
    data = config.read_bytes()
    assert old in data, "template origin url not found in .git/config"
    config.write_bytes(data.replace(old, (tmp_path / "origin.git").as_posix().encode()))
    return main


@pytest.fixture
def worktree():
    """Factory: worktree(repo, name) -> Path of a linked worktree on new branch `name` from main.

    The worktree sits beside the repo, not inside it, so a script can't find the main checkout
    by walking up from its working directory.
    """

    def make(repo: Path, name: str) -> Path:
        path = repo.parent / f"wt-{name}"
        git("worktree", "add", "-q", "-b", name, path.as_posix(), "main", cwd=repo)
        return path

    return make


@pytest.fixture
def run_script():
    """Factory: run_script(name, *args, cwd, env=None) -> CompletedProcess (text mode).

    Runs `bash payload/claude/workflow/bin/<name> *args` in cwd. `env`, when given, is merged
    over the current environment.
    """

    def run(name: str, *args: str, cwd: Path, env: dict | None = None):
        script = BIN / name
        full_env = dict(os.environ)
        if env:
            full_env.update(env)
        return subprocess.run(
            [BASH, script.as_posix(), *args],
            cwd=str(cwd),
            env=full_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=120,
        )

    return run


@pytest.fixture
def payload_text():
    """Factory: payload_text(relpath) -> the text of payload/<relpath>."""

    def read(relpath: str) -> str:
        return (PAYLOAD / relpath).read_text(encoding="utf-8")

    return read


# The suite's own guards (fast-tier budget, leak sweep, background-script helper) live in
# scripts/pad_pytest_guards.py; importing their names here registers the hooks and fixtures.
sys.path.insert(0, str(ROOT / "scripts"))
from pad_pytest_guards import (  # noqa: E402,F401
    bg,
    kill_naming,
    kill_tree,
    pytest_addoption,
    pytest_runtest_makereport,
    pytest_sessionfinish,
    real_bash,
)
