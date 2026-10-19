"""O25: suite-slot.sh shares one host-wide budget between repos.

The budget is `PAD_HOST_SLOTS`, else `Host suite slots: <n>` in the repo's config. The slots are
directories under `PAD_HOST_SLOTS_DIR`, else `~/.pad/slots`. Every test points the directory at
a temp dir, never the real home.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from conftest import BASH, git
from test_suite_slot import Slots

HOST_VARS = ("PAD_SUITE_SLOTS", "PAD_HOST_SLOTS", "PAD_HOST_SLOTS_DIR")


def _env(host_dir: Path, host_slots: str | None, repo_slots: str | None = "2") -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in HOST_VARS}
    if repo_slots is not None:
        env["PAD_SUITE_SLOTS"] = repo_slots
    env["PAD_HOST_SLOTS_DIR"] = host_dir.as_posix()
    if host_slots is not None:
        env["PAD_HOST_SLOTS"] = host_slots
    return env


def _second_repo(tmp_path: Path) -> Path:
    other = tmp_path / "other"
    other.mkdir()
    git("init", "-q", cwd=other)
    return other


def _held(host_dir: Path) -> list[str]:
    return sorted(p.name for p in host_dir.glob("[0-9]*")) if host_dir.exists() else []


@pytest.mark.slow
def test_a_host_budget_of_one_makes_the_second_repo_wait_for_the_first(repo, tmp_path):
    host = tmp_path / "host"
    s = Slots(tmp_path, repo, _env(host, "1"))
    try:
        s.start("a")
        assert s.wait(lambda: s.inside() == {"a"}), s.diag()
        s.cwd = _second_repo(tmp_path)
        s.start("b")
        s.wait(lambda: "b" in s.inside(), timeout=3)
        assert s.inside() == {"a"}, s.diag()
        assert s.release("a") == 0, s.diag()
        assert s.wait(lambda: "b" in s.inside()), s.diag()
        assert max(s.counts()) == 1, s.diag()
        assert s.release("b") == 0, s.diag()
        assert _held(host) == [], s.diag()
    finally:
        s.finish()


@pytest.mark.slow
def test_host_suite_slots_line_in_config_sets_the_budget(repo, tmp_path):
    host = tmp_path / "host"
    other = _second_repo(tmp_path)
    for r in (repo, other):
        cfg = r / ".claude" / "workflow" / "config.md"
        cfg.parent.mkdir(parents=True)
        cfg.write_text("# Config\n\n- **Host suite slots:** `1`\n- **Suite slots:** `3`\n",
                       encoding="utf-8")
    s = Slots(tmp_path, repo, _env(host, None, repo_slots=None))
    try:
        s.start("a")
        assert s.wait(lambda: s.inside() == {"a"}), s.diag()
        s.cwd = other
        s.start("b")
        s.wait(lambda: "b" in s.inside(), timeout=3)
        assert s.inside() == {"a"}, s.diag()
        assert s.release("a") == 0, s.diag()
        assert s.wait(lambda: "b" in s.inside()), s.diag()
        assert s.release("b") == 0, s.diag()
    finally:
        s.finish()


@pytest.mark.slow
def test_the_repos_own_limit_still_applies_under_a_larger_host_budget(repo, tmp_path):
    host = tmp_path / "host"
    s = Slots(tmp_path, repo, _env(host, "5", repo_slots="1"))
    try:
        s.start("a")
        assert s.wait(lambda: s.inside() == {"a"}), s.diag()
        s.start("b")
        s.wait(lambda: "b" in s.inside(), timeout=3)
        assert s.inside() == {"a"}, s.diag()
        assert s.release("a") == 0, s.diag()
        assert s.wait(lambda: "b" in s.inside()), s.diag()
        assert s.release("b") == 0, s.diag()
    finally:
        s.finish()


@pytest.mark.slow
def test_a_host_slot_whose_owner_died_is_reclaimed(repo, tmp_path):
    host = tmp_path / "host"
    (host / "1").mkdir(parents=True)
    dead = subprocess.run([BASH, "-c", "echo $$"], capture_output=True, text=True).stdout.strip()
    (host / "1" / "pid").write_text(dead + "\n", encoding="utf-8")
    s = Slots(tmp_path, repo, _env(host, "1"))
    try:
        s.start("a")
        assert s.wait(lambda: "a" in s.inside()), s.diag()
        assert s.release("a") == 0, s.diag()
    finally:
        s.finish()


@pytest.mark.slow
def test_without_a_host_budget_repos_run_as_before_and_hold_no_host_slot(repo, tmp_path):
    host = tmp_path / "host"
    s = Slots(tmp_path, repo, _env(host, None))
    try:
        s.start("a")
        s.cwd = _second_repo(tmp_path)
        s.start("b")
        assert s.wait(lambda: s.inside() == {"a", "b"}), s.diag()
        assert _held(host) == [], s.diag()
        assert s.release("a") == 0 and s.release("b") == 0, s.diag()
    finally:
        s.finish()
