"""E3-T3: triage.sh, the red-heavy triage (O23).

    triage.sh --run <id> --head <H> --base <sha> --landed K1=<merge sha>[,K2=<merge sha>...]
              --ids <test id>...                                  (run from the epic worktree)

H is the epic head the heavy tier failed at, <sha> the head before K1 landed, and the landed list
is K1..Kn in landing order with each ticket's merge commit. It prints one verdict and exits 0:

  FLAKY                       the failed ids pass when rerun alone at H (fresh process, shuffled)
  ENV                         they fail at <sha> too: not the batch's doing, nothing is reverted
  REJECTED <KEY>: heavy <ids> one ticket is the isolated cause (halving K1..Kn by running at the
                              landed merge commits in a side worktree) and its merge is reverted
                              with `git revert -m 1`

Every run goes through `pad-test.sh --role gate --ids ...`. The adapter double (test_merge_gate_tiers)
fails whenever a file BAD is in the tree it runs in, so a ticket's merge "breaks" heavy by adding it.
"""
from __future__ import annotations

import subprocess

import pytest

from conftest import BASH, BIN, git
from test_merge_gate_tiers import (ADAPTER, HEAVY_ID, RUN, REGIME, base_env, commit_files)
from test_merge_gate import _config

pytestmark = pytest.mark.slow


class Landed:
    """An epic worktree with a base commit and tickets merged one by one with --no-ff."""

    def __init__(self, repo, worktree, tmp_path, tickets: dict[str, dict[str, str]], base_files=None):
        self.repo = repo
        self.state = tmp_path / "fake-state"
        self.state.mkdir()
        self.fake_log = tmp_path / "fake.log"
        self.fake_log.write_text("", encoding="utf-8")
        self.epic = worktree(repo, "epic")
        cfg = _config(tmp_path / "cmds.log") + REGIME.format(tiers="", budget=600)
        files = {
            ".claude/workflow/config.md": cfg,
            ".claude/pad-plugins/runners/fake.sh": ADAPTER,
            ".gitignore": ".work/\n",
            "src/base.py": "BASE = 1\n",
            "tests/heavy/test_h.py": "def test_h():\n    pass\n",
        }
        files.update(base_files or {})
        self.base = commit_files(self.epic, files, "epic: base")
        self.merges: dict[str, str] = {}
        for key, tfiles in tickets.items():
            branch = f"t-{key}"
            git("checkout", "-q", "-b", branch, cwd=self.epic)
            commit_files(self.epic, tfiles, f"feat({key}): work")
            git("checkout", "-q", "epic", cwd=self.epic)
            git("merge", "-q", "--no-ff", "-m", f"Merge {key}", branch, cwd=self.epic)
            self.merges[key] = git("rev-parse", "HEAD", cwd=self.epic)
        self.head = git("rev-parse", "HEAD", cwd=self.epic)

    def triage(self, *ids: str, tickets: list[str] | None = None, **env):
        keys = tickets or list(self.merges)
        landed = ",".join(f"{k}={self.merges[k]}" for k in keys)
        return subprocess.run(
            [BASH, (BIN / "triage.sh").as_posix(), "--run", RUN, "--head", self.head,
             "--base", self.base, "--landed", landed, "--ids", *(ids or (HEAVY_ID,))],
            cwd=str(self.epic), env=base_env(self.state, self.fake_log, **env),
            capture_output=True, text=True, encoding="utf-8", timeout=170)

    def runs(self) -> list[str]:
        return [x for x in self.fake_log.read_text(encoding="utf-8").splitlines() if x.startswith("run ")]

    def run_heads(self) -> list[str]:
        return [x.rsplit("HEAD=", 1)[1] for x in self.runs()]

    def tracked(self) -> list[str]:
        return git("ls-files", cwd=self.epic).split()

    def worktrees(self) -> int:
        return len(git("worktree", "list", cwd=self.repo).splitlines())


@pytest.fixture
def landed(repo, worktree, tmp_path):
    def make(tickets, **kw) -> Landed:
        return Landed(repo, worktree, tmp_path, tickets, **kw)
    return make


def verdict(r) -> list[str]:
    return [x for x in r.stdout.splitlines() if x.startswith(("FLAKY", "ENV", "REJECTED"))]


FOUR = {
    "E9-T1": {"f1.txt": "1\n"},
    "E9-T2": {"f2.txt": "2\n"},
    "E9-T3": {"f3.txt": "3\n", "BAD": "x\n"},
    "E9-T4": {"f4.txt": "4\n"},
}


def test_o23_failed_ids_that_pass_alone_at_the_head_are_flaky_and_nothing_else_runs(landed):
    w = landed(FOUR | {"E9-T3": {"f3.txt": "3\n"}})  # nothing breaks heavy
    r = w.triage()
    assert verdict(r) == ["FLAKY"], r.stdout + r.stderr
    assert r.returncode == 0
    assert w.run_heads() == [w.head]
    assert HEAVY_ID in w.runs()[0]
    assert git("rev-parse", "HEAD", cwd=w.epic) == w.head


def test_o23_failed_ids_that_also_fail_before_the_batch_are_env_and_nothing_is_reverted(landed):
    w = landed(FOUR, base_files={"BAD": "x\n"})
    r = w.triage()
    assert verdict(r) == ["ENV"], r.stdout + r.stderr
    assert r.returncode == 0
    assert w.run_heads() == [w.head, w.base]
    assert git("rev-parse", "HEAD", cwd=w.epic) == w.head
    assert "BAD" in w.tracked()


def test_o23_a_cause_among_four_tickets_is_found_by_halving_and_only_it_is_reverted(landed):
    w = landed(FOUR)
    before = w.worktrees()
    r = w.triage()
    assert verdict(r) == [f"REJECTED E9-T3: heavy {HEAVY_ID}"], r.stdout + r.stderr
    assert r.returncode == 0
    tracked = w.tracked()
    assert "BAD" not in tracked and "f3.txt" not in tracked
    assert {"f1.txt", "f2.txt", "f4.txt"} <= set(tracked)
    assert git("log", "-1", "--format=%s", cwd=w.epic).startswith("Revert")
    assert git("rev-list", "--count", f"{w.head}..HEAD", cwd=w.epic) == "1"
    # every triage run was at the head, the base or a landed merge commit: never the revert
    allowed = {w.head, w.base, *w.merges.values()}
    assert set(w.run_heads()) <= allowed, w.run_heads()
    assert len(w.runs()) <= 5, w.runs()
    assert w.worktrees() == before, "the side worktree was left behind"


def test_o23_the_first_of_several_tickets_can_be_the_isolated_cause(landed):
    w = landed({"E9-T1": {"BAD": "x\n"}, "E9-T2": {"f2.txt": "2\n"}, "E9-T3": {"f3.txt": "3\n"}})
    r = w.triage()
    assert verdict(r) == [f"REJECTED E9-T1: heavy {HEAVY_ID}"], r.stdout + r.stderr
    assert "BAD" not in w.tracked()
    assert {"f2.txt", "f3.txt"} <= set(w.tracked())


def test_o23_a_single_landed_ticket_that_breaks_heavy_is_reverted_without_halving(landed):
    w = landed({"E9-T1": {"BAD": "x\n"}})
    r = w.triage()
    assert verdict(r) == [f"REJECTED E9-T1: heavy {HEAVY_ID}"], r.stdout + r.stderr
    assert "BAD" not in w.tracked()
    assert w.run_heads() == [w.head, w.base]
