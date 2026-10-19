"""merge-candidate.sh: the combined tree of several READY tickets, built in a throwaway worktree.

    merge-candidate.sh --worktree <epic worktree> --branch <epic branch> --run <id>
                       [--deps <dir>] [--derived "<path>=<cmd>" ...] [--test-paths "<pathspecs>"]
                       <KEY>...
    merge-candidate.sh --remove <path>

Each KEY's `<KEY> <TASK_HEAD> <RED>` line is read from <main checkout>/.work/runs/<id>/merge-queue.
Prints CANDIDATE <path>, then per ticket in order PREFIX <KEY> <commit> <tree> (the candidate
after that ticket), CONFLICT <KEY>: <paths> or REJECTED <KEY>: <reason>. A ticket that conflicts or
is rejected is left out and the next one is tried on what was built so far.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from conftest import git

pytestmark = pytest.mark.slow

COUNT = "COUNT.md"
REBUILD = f"{COUNT}=printf 'modules: %s\\n' \"$(ls src | wc -l | tr -d ' ')\" > {COUNT}"
RUN = "R1"


def _commit(wt: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        p = wt / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        git("add", rel, cwd=wt)
    git("commit", "-q", "-m", msg, cwd=wt)
    return git("rev-parse", "HEAD", cwd=wt)


def _epic(repo: Path, worktree, base: dict[str, str] | None = None) -> tuple[Path, str]:
    wt = worktree(repo, "epic")
    head = _commit(wt, {"src/base.py": "BASE = 1\n", **(base or {})}, "epic: base")
    git("push", "-q", "-u", "origin", "epic", cwd=wt)
    return wt, head


def _ticket(repo: Path, worktree, epic_head: str, key: str, files: dict[str, str],
            edit_red: bool = False) -> tuple[str, str]:
    """A task on the epic head: a red test commit, then a code commit. -> (red, head)."""
    wt = worktree(repo, key.lower())
    git("reset", "-q", "--hard", epic_head, cwd=wt)
    test = f"tests/test_{key.lower()}.py"
    red = _commit(wt, {test: "def test_new():\n    assert False\n"}, f"test({key}): O1 [red]")
    head = _commit(wt, files, f"feat({key}): impl")
    if edit_red:
        head = _commit(wt, {test: "def test_new():\n    assert True\n"}, f"feat({key}): edit test")
    return red, head


def _queue(repo: Path, rows: dict[str, tuple[str, str]]) -> None:
    d = repo / ".work" / "runs" / RUN
    d.mkdir(parents=True, exist_ok=True)
    (d / "merge-queue").write_text(
        "".join(f"{k} {head} {red}\n" for k, (red, head) in rows.items()), encoding="utf-8")


def _candidate(run_script, repo: Path, epic: Path, *keys: str, extra: tuple[str, ...] = ()):
    return run_script("merge-candidate.sh", "--worktree", epic.as_posix(), "--branch", "epic",
                      "--run", RUN, *extra, *keys, cwd=repo)


def _lines(r, word: str) -> list[list[str]]:
    return [ln.split() for ln in r.stdout.splitlines() if ln.split()[:1] == [word]]


def _cand_path(r) -> Path:
    found = _lines(r, "CANDIDATE")
    assert len(found) == 1, r.stdout + r.stderr
    return Path(found[0][1])


def _worktrees(cwd: Path) -> str:
    return git("worktree", "list", "--porcelain", cwd=cwd).replace("\\", "/")


def _three_with_conflicting_second(repo, worktree):
    epic, head = _epic(repo, worktree)
    t1 = _ticket(repo, worktree, head, "K1", {"src/shared.py": "S = 'one'\n", "src/k1.py": "A = 1\n"})
    t2 = _ticket(repo, worktree, head, "K2", {"src/shared.py": "S = 'two'\n", "src/k2.py": "B = 2\n"})
    t3 = _ticket(repo, worktree, head, "K3", {"src/k3.py": "C = 3\n"})
    _queue(repo, {"K1": t1, "K2": t2, "K3": t3})
    return epic, head


def test_o6_conflicting_second_ticket_is_left_out_and_prefixes_cover_k1_and_k3(
        repo, worktree, run_script):
    epic, head = _three_with_conflicting_second(repo, worktree)
    r = _candidate(run_script, repo, epic, "K1", "K2", "K3")
    assert r.returncode == 0, r.stdout + r.stderr
    cand = _cand_path(r)
    assert "pad-candidate" in cand.as_posix()
    prefix = {p[1]: p for p in _lines(r, "PREFIX")}
    assert sorted(prefix) == ["K1", "K3"], r.stdout
    conflict = [ln for ln in r.stdout.splitlines() if ln.startswith("CONFLICT ")]
    assert len(conflict) == 1 and conflict[0].startswith("CONFLICT K2: ")
    assert "src/shared.py" in conflict[0]
    # PREFIX <KEY> <commit> <tree>: the commit's tree is the printed tree; K3's holds K1 and K3.
    for key in ("K1", "K3"):
        assert git("rev-parse", f"{prefix[key][2]}^{{tree}}", cwd=cand) == prefix[key][3]
    assert git("show", f"{prefix['K1'][2]}:src/k1.py", cwd=cand) == "A = 1"
    assert git("show", f"{prefix['K3'][2]}:src/k1.py", cwd=cand) == "A = 1"
    assert git("show", f"{prefix['K3'][2]}:src/k3.py", cwd=cand) == "C = 3"
    assert git("show", f"{prefix['K3'][2]}:src/shared.py", cwd=cand) == "S = 'one'"
    assert subprocess.run(["git", "cat-file", "-e", f"{prefix['K3'][2]}:src/k2.py"], cwd=str(cand),
                          capture_output=True).returncode != 0


def test_o6_candidate_is_a_detached_worktree_at_the_epic_head(repo, worktree, run_script):
    epic, head = _three_with_conflicting_second(repo, worktree)
    r = _candidate(run_script, repo, epic, "K1", "K2", "K3")
    cand = _cand_path(r)
    assert cand.as_posix() in _worktrees(repo)
    assert subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=str(cand),
                          capture_output=True).returncode != 0
    first = _lines(r, "PREFIX")[0]
    assert git("rev-parse", f"{first[2]}^1", cwd=cand) == head


def test_o6_epic_worktree_is_untouched(repo, worktree, run_script):
    epic, head = _three_with_conflicting_second(repo, worktree)
    origin_before = git("rev-parse", "refs/heads/epic", cwd=repo.parent / "origin.git")
    r = _candidate(run_script, repo, epic, "K1", "K2", "K3")
    assert r.returncode == 0, r.stdout + r.stderr
    assert git("rev-parse", "HEAD", cwd=epic) == head
    assert git("symbolic-ref", "--short", "HEAD", cwd=epic) == "epic"
    assert git("status", "--porcelain", cwd=epic) == ""
    assert not (epic / "src" / "k1.py").is_file()
    assert git("rev-parse", "refs/heads/epic", cwd=repo.parent / "origin.git") == origin_before


def test_o6_candidate_links_the_dependency_directory(repo, worktree, run_script):
    epic, head = _three_with_conflicting_second(repo, worktree)
    (epic / "node_modules").mkdir()
    (epic / "node_modules" / "marker.txt").write_text("installed\n", encoding="utf-8")
    r = _candidate(run_script, repo, epic, "K1", "K2", "K3", extra=("--deps", "node_modules"))
    cand = _cand_path(r)
    assert (cand / "node_modules" / "marker.txt").read_text(encoding="utf-8").strip() == "installed"


def test_o6_ticket_failing_submission_is_rejected_and_the_rest_are_built(
        repo, worktree, run_script):
    epic, head = _epic(repo, worktree)
    t1 = _ticket(repo, worktree, head, "K1", {"src/k1.py": "A = 1\n"}, edit_red=True)
    t2 = _ticket(repo, worktree, head, "K2", {"src/k2.py": "B = 2\n"})
    _queue(repo, {"K1": t1, "K2": t2})
    r = _candidate(run_script, repo, epic, "K1", "K2")
    rejected = [ln for ln in r.stdout.splitlines() if ln.startswith("REJECTED ")]
    assert len(rejected) == 1 and rejected[0].startswith("REJECTED K1: "), r.stdout + r.stderr
    assert "test-changed-after-red" in rejected[0]
    prefix = _lines(r, "PREFIX")
    assert [p[1] for p in prefix] == ["K2"]
    assert git("show", f"{prefix[0][2]}:src/k2.py", cwd=_cand_path(r)) == "B = 2"


def test_remove_deletes_the_candidate_worktree(repo, worktree, run_script):
    epic, head = _three_with_conflicting_second(repo, worktree)
    cand = _cand_path(_candidate(run_script, repo, epic, "K1", "K3"))
    assert cand.as_posix() in _worktrees(repo)
    r = run_script("merge-candidate.sh", "--remove", cand.as_posix(), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == ""
    assert cand.as_posix() not in _worktrees(repo)
    assert git("rev-parse", "HEAD", cwd=epic) == head
    assert git("status", "--porcelain", cwd=epic) == ""


def test_o7_derived_only_conflicts_give_the_trees_that_landing_with_merge_task_produces(
        repo, worktree, run_script):
    epic, head = _epic(repo, worktree, {COUNT: "modules: 1\n"})
    t1 = _ticket(repo, worktree, head, "K1", {"src/k1.py": "A = 1\n", COUNT: "modules: 2 (k1)\n"})
    t2 = _ticket(repo, worktree, head, "K2", {"src/k2.py": "B = 2\n", COUNT: "modules: 2 (k2)\n"})
    t3 = _ticket(repo, worktree, head, "K3", {"src/k3.py": "C = 3\n", COUNT: "modules: 2 (k3)\n"})
    _queue(repo, {"K1": t1, "K2": t2, "K3": t3})
    r = _candidate(run_script, repo, epic, "K1", "K2", "K3", extra=("--derived", REBUILD))
    assert r.returncode == 0, r.stdout + r.stderr
    prefix = _lines(r, "PREFIX")
    assert [p[1] for p in prefix] == ["K1", "K2", "K3"], r.stdout
    cand = _cand_path(r)
    assert git("show", f"{prefix[2][2]}:{COUNT}", cwd=cand) == "modules: 4"
    assert git("rev-parse", "HEAD", cwd=epic) == head
    for (key, (red, tip)), p in zip({"K1": t1, "K2": t2, "K3": t3}.items(), prefix):
        m = run_script("merge-task.sh", "--worktree", epic.as_posix(), "--branch", "epic",
                       "--derived", REBUILD, "--gate", "true", "--lint", "true",
                       key, red, tip, f"land {key}", cwd=repo)
        assert m.stdout.strip().splitlines()[-1].startswith("MERGED "), m.stdout + m.stderr
        assert git("rev-parse", "HEAD^{tree}", cwd=epic) == p[3], key
