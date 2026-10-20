"""E3-T4 O40: a non-suite ticket's diff may not touch the protected surface.

`submit-surface.sh <epic head> <task head> [--ticket <path>]` runs in the task's worktree and
prints `needs-suite-owner: <path>` for each changed path on the surface, exit 1; nothing and
exit 0 otherwise. `task-submit.sh` calls it for every submit (`SUBMIT FAIL needs-suite-owner:
<path>`), so `merge-task.sh`, which runs `task-submit.sh`, rejects the same diff.

The surface: managed (`.claude/workflow/**`, `.claude/settings.json`, CI workflow files,
`.pre-commit-config.yaml`, the suite map: config `Suite map:` under `## Test regime`, default
`tests/MAP.md`), plus the runner adapter's `protected-files` globs, plus the globs the config's
`Protected surface:` line lists in backticks. A ticket whose `## Domain` is `suite` may change it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from conftest import git
from test_task_submit import _branch, _commit, _epic, _last, _red

ADAPTER = """#!/usr/bin/env bash
case "$1" in
  protected-files) echo "fakecfg.ini" ;;
  runner-names) echo "fakecmd" ;;
  capabilities) echo "" ;;
  acceptance-pattern) echo "*$2*" ;;
esac
exit 0
"""

REGIME = """# Workflow config

## Test regime

- **Runner:** `fake`
- **Suite map:** `docs/suite-map.md`
- **Protected surface:** `ops/*.yml`, `infra/**`
"""

MANAGED = [
    ".claude/settings.json",
    ".claude/workflow/bin/helper.sh",
    ".claude/workflow/config.md",
    ".github/workflows/ci.yml",
    ".pre-commit-config.yaml",
    "tests/MAP.md",
]


def _setup(repo: Path, worktree, change: dict[str, str], *, regime: bool = False):
    """A task branch whose head changes `change`; returns (wt, epic, red, head)."""
    epic = _epic(repo)
    if regime:
        epic = _commit(repo, {
            ".claude/workflow/config.md": REGIME,
            ".claude/pad-plugins/runners/fake.sh": ADAPTER,
        }, "epic: regime config and adapter")
    wt = _branch(repo, worktree, "t-surface", epic)
    red = _red(wt)
    head = _commit(wt, change, "feat(T-1): change")
    return wt, epic, red, head


def _surface(run_script, wt: Path, epic: str, head: str, *extra: str):
    return run_script("submit-surface.sh", epic, head, *extra, cwd=wt)


def _ticket(tmp_path: Path, domain: str, owns: str) -> Path:
    p = tmp_path / "T-1.md"
    p.write_text(f"## Outcome\nx\n\n## Domain\n{domain}\n\n## Owns\n- {owns}\n\n## Touches\nnone\n",
                 encoding="utf-8")
    return p


@pytest.mark.slow
@pytest.mark.parametrize("path", MANAGED)
def test_o40_a_managed_surface_path_needs_the_suite_owner(repo, worktree, run_script, path):
    wt, epic, _red_sha, head = _setup(repo, worktree, {path: "x\n"})
    r = _surface(run_script, wt, epic, head)
    assert r.returncode == 1, r.stdout + r.stderr
    assert r.stdout.strip().splitlines() == [f"needs-suite-owner: {path}"]


@pytest.mark.slow
def test_o40_a_diff_off_the_surface_passes_silently(repo, worktree, run_script):
    wt, epic, _red_sha, head = _setup(repo, worktree, {"src/impl.py": "X = 1\n"})
    r = _surface(run_script, wt, epic, head)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == ""


@pytest.mark.slow
def test_o40_every_surface_path_in_the_diff_is_named(repo, worktree, run_script):
    wt, epic, _red_sha, head = _setup(repo, worktree, {
        ".pre-commit-config.yaml": "x\n", "src/impl.py": "X = 1\n", ".claude/settings.json": "{}\n"})
    r = _surface(run_script, wt, epic, head)
    assert r.returncode == 1
    assert sorted(r.stdout.strip().splitlines()) == [
        "needs-suite-owner: .claude/settings.json", "needs-suite-owner: .pre-commit-config.yaml"]


@pytest.mark.slow
def test_o40_the_configured_suite_map_is_on_the_surface(repo, worktree, run_script):
    wt, epic, _red_sha, head = _setup(repo, worktree, {"docs/suite-map.md": "x\n"}, regime=True)
    r = _surface(run_script, wt, epic, head)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "needs-suite-owner: docs/suite-map.md" in r.stdout


@pytest.mark.slow
def test_o40_the_adapters_protected_files_are_on_the_surface(repo, worktree, run_script):
    wt, epic, _red_sha, head = _setup(repo, worktree, {"fakecfg.ini": "x\n"}, regime=True)
    r = _surface(run_script, wt, epic, head)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "needs-suite-owner: fakecfg.ini" in r.stdout


@pytest.mark.slow
@pytest.mark.parametrize("path", ["ops/deploy.yml", "infra/net/main.tf"])
def test_o40_the_repos_own_additions_are_on_the_surface(repo, worktree, run_script, path):
    wt, epic, _red_sha, head = _setup(repo, worktree, {path: "x\n"}, regime=True)
    r = _surface(run_script, wt, epic, head)
    assert r.returncode == 1, r.stdout + r.stderr
    assert f"needs-suite-owner: {path}" in r.stdout


@pytest.mark.slow
def test_o40_a_suite_ticket_may_change_the_surface(repo, worktree, run_script, tmp_path):
    wt, epic, _red_sha, head = _setup(repo, worktree, {".pre-commit-config.yaml": "x\n"})
    ticket = _ticket(tmp_path, "suite", ".pre-commit-config.yaml")
    r = _surface(run_script, wt, epic, head, "--ticket", ticket.as_posix())
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == ""


@pytest.mark.slow
def test_o40_task_submit_rejects_a_surface_path_for_a_non_suite_ticket(repo, worktree, run_script):
    wt, epic, red, head = _setup(repo, worktree, {".claude/settings.json": "{}\n"})
    r = run_script("task-submit.sh", epic, red, head, "--test-paths", "tests", cwd=wt)
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r) == "SUBMIT FAIL needs-suite-owner: .claude/settings.json"


@pytest.mark.slow
def test_o40_owning_a_surface_path_does_not_lift_the_rule_for_a_non_suite_ticket(
    repo, worktree, run_script, tmp_path
):
    wt, epic, red, head = _setup(repo, worktree, {".claude/settings.json": "{}\n"})
    ticket = _ticket(tmp_path, "regime", ".claude/settings.json")
    r = run_script("task-submit.sh", epic, red, head, "--test-paths", "tests",
                   "--ticket", ticket.as_posix(), cwd=wt)
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r) == "SUBMIT FAIL needs-suite-owner: .claude/settings.json"


@pytest.mark.slow
def test_o40_task_submit_accepts_a_suite_ticket_on_the_surface(repo, worktree, run_script, tmp_path):
    wt, epic, red, head = _setup(repo, worktree, {".claude/settings.json": "{}\n"})
    ticket = _ticket(tmp_path, "suite", ".claude/settings.json")
    plain = run_script("task-submit.sh", epic, red, head, "--test-paths", "tests", cwd=wt)
    assert _last(plain) == "SUBMIT FAIL needs-suite-owner: .claude/settings.json"
    r = run_script("task-submit.sh", epic, red, head, "--test-paths", "tests",
                   "--ticket", ticket.as_posix(), cwd=wt)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == "SUBMIT OK"


@pytest.mark.slow
def test_o40_merge_task_protected_rejects_a_surface_path_with_the_same_reason(
    repo, worktree, run_script
):
    """`merge-task.sh --protected` runs task-submit.sh, so the rejection carries its reason."""
    epic_wt = worktree(repo, "epic")
    epic_head = git("rev-parse", "HEAD", cwd=epic_wt)
    wt = repo.parent / "wt-t-merge"
    git("worktree", "add", "-q", "-b", "t-merge", wt.as_posix(), epic_head, cwd=repo)
    red = _red(wt)
    head = _commit(wt, {".pre-commit-config.yaml": "x\n"}, "feat(T-1): change")
    r = run_script("merge-task.sh", "--worktree", epic_wt.as_posix(), "--branch", "epic",
                   "--protected", "src/db/**", "--gate", "true", "--lint", "true",
                   "T-1", red, head, "goal", cwd=repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r) == "REJECTED T-1: needs-suite-owner: .pre-commit-config.yaml"
