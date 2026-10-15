"""cleanup-run.sh removes a run's residue once its epic PR has merged.

    cleanup-run.sh --run <id> --epic-branch <b> [--dry-run]

Refused unless the epic tip is in origin/<default> after a fetch, or `gh pr view <b>` says
MERGED (squash merges). Then: the run's worktrees (epic branch, board.md branches, or
.claude/worktrees/<id>), their local branches, the epic's remote branch, stale pad-locks and
pad-preview pid files, `git worktree prune`, and .work/runs/<id>/. A dirty worktree is skipped
with its branch. Last line `CLEANUP OK <n> removed` | `CLEANUP REFUSED <why>` |
`CLEANUP PARTIAL <n> skipped`. `gh` is always a stub here, so no test reaches the network.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from conftest import git

RUN = "E7"
EPIC = "epic-E7"

GH = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >> "$STUB_LOG"
[ "${GH_STATE:-}" = fail ] && exit 1
printf '%s\n' "${GH_STATE:-OPEN}"
"""


@pytest.fixture
def gh(tmp_path):
    d = tmp_path / "stubs"
    d.mkdir()
    p = d / "gh"
    p.write_bytes(GH.encode("utf-8"))
    os.chmod(p, 0o755)
    posix = d.as_posix()
    if len(posix) > 1 and posix[1] == ":":
        posix = "/" + posix[0].lower() + posix[2:]
    rc = tmp_path / "stub-env.sh"
    rc.write_bytes(f'PATH="{posix}:$PATH"\n'.encode("utf-8"))
    log = tmp_path / "stub.log"

    def env(state: str = "OPEN") -> dict:
        return {"BASH_ENV": rc.as_posix(), "STUB_LOG": log.as_posix(), "GH_STATE": state}

    env.log = log
    return env


def _commit(wt: Path, name: str, text: str = "x\n") -> None:
    (wt / name).write_bytes(text.encode("utf-8"))
    git("add", name, cwd=wt)
    git("commit", "-q", "-m", f"add {name}", cwd=wt)


def _branches(repo: Path) -> set[str]:
    return set(git("for-each-ref", "--format=%(refname:short)", "refs/heads", cwd=repo).split())


def _remote_heads(repo: Path) -> str:
    return git("ls-remote", "--heads", "origin", cwd=repo)


def _last(r) -> str:
    lines = r.stdout.strip().splitlines()
    return lines[-1] if lines else ""


def _setup(repo: Path, worktree, merged: bool = True, squash: bool = False):
    """An epic with two ticket worktrees, a run-named worktree, an unrelated one, run files, locks."""
    epic = worktree(repo, EPIC)
    t1 = worktree(repo, "E7-T1")
    t2 = worktree(repo, "E7-T2")
    _commit(t1, "t1.txt")
    _commit(t2, "t2.txt")
    git("merge", "-q", "--no-ff", "-m", "land T1", "E7-T1", cwd=epic)
    git("merge", "-q", "--no-ff", "-m", "land T2", "E7-T2", cwd=epic)
    git("push", "-q", "origin", EPIC, cwd=epic)
    if merged:
        git("merge", "-q", "--no-ff", "-m", "merge epic", EPIC, cwd=repo)
        git("push", "-q", "origin", "main", cwd=repo)
    elif squash:
        git("merge", "-q", "--squash", EPIC, cwd=repo)
        git("commit", "-q", "-m", "squash epic", cwd=repo)
        git("push", "-q", "origin", "main", cwd=repo)

    scratch = repo / ".claude" / "worktrees" / RUN
    git("worktree", "add", "-q", "-b", "scratch-E7", scratch.as_posix(), "main", cwd=repo)
    other = worktree(repo, "other")

    run = repo / ".work" / "runs" / RUN
    run.mkdir(parents=True)
    (run / "board.md").write_bytes(
        b"# Board: E7\n\n| Key | Owner | Status | Branch | Sha | Evidence |\n|---|---|---|---|---|---|\n"
        b"| E7-T1 | a1 | done | E7-T1 | 1111111 | - |\n"
        b"| E7-T2 | a2 | done | E7-T2 | 2222222 | - |\n"
        b"| E7-T3 | - | todo | - | - | - |\n")
    (run / "progress.md").write_bytes(b"x\n")
    tickets = repo / ".work" / "tickets" / RUN
    tickets.mkdir(parents=True)
    (tickets / "E7-T1.md").write_bytes(b"---\nstatus: done\n---\n")

    common = repo / ".git"
    (common / "pad-locks" / "slots" / "1").mkdir(parents=True)
    (common / "pad-locks" / "slots" / "1" / "pid").write_bytes(b"999999\n")
    (common / "pad-preview").mkdir()
    (common / "pad-preview" / "web.pid").write_bytes(b"999998\n")
    (common / "pad-preview" / "web.log").write_bytes(b"log\n")
    return {"epic": epic, "t1": t1, "t2": t2, "scratch": scratch, "other": other, "run": run,
            "tickets": tickets, "common": common}


def _cleanup(run_script, repo, env, *extra):
    return run_script("cleanup-run.sh", "--run", RUN, "--epic-branch", EPIC, *extra, cwd=repo, env=env)


def test_merged_epic_removes_everything_of_the_run(repo, worktree, run_script, gh):
    s = _setup(repo, worktree)

    r = _cleanup(run_script, repo, gh("OPEN"))

    assert r.returncode == 0, r.stdout + r.stderr
    for k in ("epic", "t1", "t2", "scratch"):
        assert not s[k].exists(), k
    assert s["other"].exists()
    branches = _branches(repo)
    assert not branches & {EPIC, "E7-T1", "E7-T2", "scratch-E7"}
    assert {"main", "other"} <= branches
    assert f"refs/heads/{EPIC}" not in _remote_heads(repo)
    assert "refs/heads/main" in _remote_heads(repo)
    assert not (s["common"] / "pad-locks" / "slots" / "1").exists()
    assert not (s["common"] / "pad-preview" / "web.pid").exists()
    assert not s["run"].exists()
    assert (s["tickets"] / "E7-T1.md").is_file()
    assert git("worktree", "list", "--porcelain", cwd=repo).count("worktree ") == 2

    out = r.stdout
    assert f"DELETED remote {EPIC}" in out
    assert "DELETED branch E7-T1" in out
    assert "REMOVED run " in out
    assert sum(1 for l in out.splitlines() if l.startswith("REMOVED worktree ")) == 4
    n = sum(1 for l in out.splitlines() if l.startswith(("REMOVED ", "DELETED ")))
    assert _last(r) == f"CLEANUP OK {n} removed"


def test_unmerged_epic_is_refused_and_nothing_changes(repo, worktree, run_script, gh):
    s = _setup(repo, worktree, merged=False)
    before = _branches(repo)

    r = _cleanup(run_script, repo, gh("OPEN"))

    assert r.returncode == 1
    assert _last(r).startswith("CLEANUP REFUSED ")
    for k in ("epic", "t1", "t2", "scratch", "run"):
        assert s[k].exists(), k
    assert _branches(repo) == before
    assert f"refs/heads/{EPIC}" in _remote_heads(repo)
    assert (s["common"] / "pad-preview" / "web.pid").exists()
    assert not any(l.startswith(("REMOVED", "DELETED")) for l in r.stdout.splitlines())


def test_gh_failure_counts_as_not_merged(repo, worktree, run_script, gh):
    s = _setup(repo, worktree, merged=False)

    r = _cleanup(run_script, repo, gh("fail"))

    assert r.returncode == 1
    assert _last(r).startswith("CLEANUP REFUSED ")
    assert s["epic"].exists()


def test_squash_merge_accepted_through_gh(repo, worktree, run_script, gh):
    s = _setup(repo, worktree, merged=False, squash=True)

    r = _cleanup(run_script, repo, gh("MERGED"))

    assert r.returncode == 0, r.stdout + r.stderr
    assert not s["epic"].exists()
    assert EPIC not in _branches(repo)
    assert EPIC in gh.log.read_text(encoding="utf-8")


def test_dirty_worktree_is_skipped_with_its_branch(repo, worktree, run_script, gh):
    s = _setup(repo, worktree)
    (s["t1"] / "notes.txt").write_bytes(b"unsaved\n")       # untracked, not ignored
    (s["t2"] / "t2.txt").write_bytes(b"changed\n")           # uncommitted change

    r = _cleanup(run_script, repo, gh("OPEN"))

    assert r.returncode == 1
    assert s["t1"].exists() and (s["t1"] / "notes.txt").exists()
    assert s["t2"].exists()
    assert {"E7-T1", "E7-T2"} <= _branches(repo)
    assert not s["epic"].exists()
    assert EPIC not in _branches(repo)
    assert any(l.startswith("SKIP ") and "wt-E7-T1" in l and l.endswith(": dirty") for l in r.stdout.splitlines())
    assert s["run"].exists()                                 # kept so a rerun finds the board
    skipped = sum(1 for l in r.stdout.splitlines() if l.startswith("SKIP "))
    assert _last(r) == f"CLEANUP PARTIAL {skipped} skipped"


def test_ignored_files_do_not_make_a_worktree_dirty(repo, worktree, run_script, gh):
    _commit(repo, ".gitignore", "node_modules/\n")
    git("push", "-q", "origin", "main", cwd=repo)
    s = _setup(repo, worktree)
    (s["t1"] / "node_modules").mkdir()
    (s["t1"] / "node_modules" / "pkg.js").write_bytes(b"x\n")

    r = _cleanup(run_script, repo, gh("OPEN"))

    assert r.returncode == 0, r.stdout + r.stderr
    assert not s["t1"].exists()


def test_dry_run_changes_nothing(repo, worktree, run_script, gh):
    s = _setup(repo, worktree)
    before = _branches(repo)
    wts = git("worktree", "list", "--porcelain", cwd=repo)

    r = _cleanup(run_script, repo, gh("OPEN"), "--dry-run")

    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.strip().splitlines()
    acts = [l for l in lines[:-1] if l.strip()]
    assert acts and all(l.startswith("WOULD ") for l in acts), lines
    assert any(l.startswith("WOULD REMOVED worktree ") for l in acts)
    assert f"WOULD DELETED remote {EPIC}" in acts
    assert _last(r).startswith("CLEANUP OK ")
    for k in ("epic", "t1", "t2", "scratch", "run"):
        assert s[k].exists(), k
    assert _branches(repo) == before
    assert git("worktree", "list", "--porcelain", cwd=repo) == wts
    assert f"refs/heads/{EPIC}" in _remote_heads(repo)
    assert (s["common"] / "pad-preview" / "web.pid").exists()


def test_absent_remote_branch_is_skipped_quietly(repo, worktree, run_script, gh):
    s = _setup(repo, worktree)
    git("push", "-q", "origin", "--delete", EPIC, cwd=repo)

    r = _cleanup(run_script, repo, gh("OPEN"))

    assert r.returncode == 0, r.stdout + r.stderr
    assert not any(" remote " in f" {l} " and not l.startswith("REMOVED") for l in r.stdout.splitlines())
    assert not s["epic"].exists()


def test_runs_from_a_linked_worktree(repo, worktree, run_script, gh):
    s = _setup(repo, worktree)

    r = _cleanup(run_script, s["other"], gh("OPEN"))

    assert r.returncode == 0, r.stdout + r.stderr
    assert not s["run"].exists()
    assert not s["epic"].exists()


@pytest.mark.parametrize("args", [[], ["--run", RUN], ["--epic-branch", EPIC],
                                  ["--run", RUN, "--epic-branch", EPIC, "--bogus"]])
def test_usage(repo, run_script, gh, args):
    r = run_script("cleanup-run.sh", *args, cwd=repo, env=gh("MERGED"))
    assert r.returncode == 64
