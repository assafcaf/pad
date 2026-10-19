"""E2-T10: the shipped `batch` strategy gates up to `max` queued tickets once as a candidate
(O12, O13, O14, O28).

batch.sh is driven directly, with a copy of the bin directory as PAD_BIN whose building blocks
log their calls, the way merge.sh would call it.
"""
from __future__ import annotations

import math
import os
import re
import shutil
import subprocess

import pytest

from conftest import BASH, BIN, PAYLOAD, git
from test_merge_strategies import write_config
from test_merge_task import _commit
from test_merge_ticket import CONFIG, KEY, RUN, TICKET, _setup

BATCH = PAYLOAD / "claude" / "workflow" / "merge-strategies" / "batch.sh"
WRAPPED = ("merge-gate.sh", "merge-candidate.sh", "merge-ticket.sh")


def test_o12_the_shipped_batch_files_validate_clean(run_script, tmp_path):
    cwd = tmp_path / "work"
    cwd.mkdir()
    write_config(cwd, "batch max=2")
    r = run_script("merge-strategies.sh", "validate", cwd=cwd)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "STRATEGY FAIL" not in r.stdout
    names = run_script("merge-strategies.sh", "list", cwd=cwd).stdout
    assert re.search(r"^batch\t", names, re.M), names


class Batch:
    def __init__(self, repo, worktree, tmp_path, *, bad=None, count=3, gate_override=None):
        self.repo, self.tmp = repo, tmp_path
        self.epic, self.epic_head, red, head = _setup(repo, worktree)
        self.gates = tmp_path / "gate-runs"
        full = f"echo g >> {self.gates.as_posix()}; ! grep -rq BAD src"
        cfg = repo / ".claude" / "workflow" / "config.md"
        cfg.write_text(CONFIG.replace('`grep -q "X = 1" src/impl.py`', f"`{full}`"),
                       encoding="utf-8")
        rows = {KEY: (red, head)}
        for n in range(2, count + 1):
            impl = "BAD = 1\n" if f"E1-T{n}" == bad else f"Y{n} = 1\n"
            rows[f"E1-T{n}"] = self._ticket(worktree, n, impl)
        self.keys = list(rows)
        self.lines = [f"{k} {h} {r}\n" for k, (r, h) in rows.items()]
        self.stdin = "".join(self.lines)
        run_dir = repo / ".work" / "runs" / RUN
        (run_dir / "merge-queue").write_text(self.stdin, encoding="utf-8")
        # a copy of bin whose building blocks log their calls
        self.bin = tmp_path / "bin"
        shutil.copytree(BIN, self.bin)
        self.log = tmp_path / "calls"
        for name in WRAPPED:
            self.wrap(name, f'bash "{(BIN / name).as_posix()}" "$@"')
        if gate_override:
            self.wrap("merge-gate.sh", gate_override)

    def wrap(self, name, body):
        text = (f'#!/usr/bin/env bash\necho "{name} $*" >> "{self.log.as_posix()}"\n{body}\n')
        (self.bin / name).write_bytes(text.encode("utf-8"))

    def _ticket(self, worktree, n, impl):
        key = f"E1-T{n}"
        t = self.repo / ".work" / "runs" / RUN / "tickets" / f"{key}.md"
        text = (TICKET.replace("{protected}", "no").replace(KEY, key)
                .replace("src/impl.py", f"src/impl{n}.py")
                .replace("tests/test_new.py", f"tests/test_new{n}.py"))
        t.write_bytes(text.encode("utf-8"))
        tracker = self.repo / ".work" / "tickets" / "E1" / f"{key}.md"
        tracker.write_bytes(f"---\nkey: {key}\nstatus: doing\n---\n\n## Outcome\nx\n".encode())
        wt = worktree(self.repo, f"task{n}")
        git("reset", "-q", "--hard", self.epic_head, cwd=wt)
        red = _commit(wt, {f"tests/test_new{n}.py": "def test_new():\n    assert False\n"},
                      f"test({key}): O1 [red]")
        head = _commit(wt, {f"src/impl{n}.py": impl}, f"feat({key}): impl")
        return red, head

    def run(self, stdin=None, max_=8):
        env = {**os.environ, "PAD_RUN": RUN, "PAD_BIN": self.bin.as_posix(),
               "PAD_EPIC_WORKTREE": self.epic.as_posix(), "PAD_EPIC_BRANCH": "epic",
               "PAD_MERGE_LOCK_HELD": "1", "PAD_OPT_MAX": str(max_)}
        return subprocess.run([BASH, BATCH.as_posix()], cwd=str(self.repo), env=env,
                              input=self.stdin if stdin is None else stdin, text=True,
                              encoding="utf-8", capture_output=True, timeout=900)

    def calls(self, name):
        if not self.log.exists():
            return []
        return [ln[len(name) + 1:] for ln in self.log.read_text(encoding="utf-8").splitlines()
                if ln.startswith(name + " ")]

    def gate_runs(self):
        return len(self.gates.read_text().splitlines()) if self.gates.exists() else 0

    def merges(self):
        return git("log", "--merges", "--reverse", "--format=%s", f"{self.epic_head}..HEAD",
                   cwd=self.epic).splitlines()


def keys_of(call):
    return re.findall(r"\bE1-T\d\b", call)


@pytest.fixture
def make(repo, worktree, tmp_path):
    return lambda **kw: Batch(repo, worktree, tmp_path, **kw)


@pytest.mark.slow
def test_o12_three_clean_tickets_are_gated_once_and_land_in_queue_order(make):
    b = make()
    r = b.run()
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    merged = re.findall(r"^MERGED (\S+) ([0-9a-f]{40})$", r.stdout, re.M)
    assert [k for k, _ in merged] == b.keys[:3], out
    assert b.gate_runs() == 1, out
    assert [s.split(":")[0] for s in b.merges()] == [f"Merge {k}" for k in b.keys[:3]]
    assert git("rev-parse", "HEAD", cwd=b.epic) == merged[-1][1]
    tickets = b.calls("merge-ticket.sh")
    assert len(tickets) == 3 and all("--expect-tree" in t for t in tickets), tickets
    trees = [re.search(r"--expect-tree (\S+)", t).group(1) for t in tickets]
    assert git("rev-parse", "HEAD^{tree}", cwd=b.epic) == trees[-1]
    assert not [ln for ln in git("worktree", "list", cwd=b.epic).splitlines()
                if "pad-candidate" in ln.replace("\\", "/")]


@pytest.mark.slow
def test_o13_third_ticket_breaks_the_gate_so_two_land_one_is_rejected_one_requeued(make):
    b = make(count=4, bad="E1-T3")
    r = b.run()
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    lines = r.stdout.splitlines()
    assert [ln.split()[1] for ln in lines if ln.startswith("MERGED ")] == b.keys[:2], out
    assert any(ln.startswith(f"REJECTED {b.keys[2]}: gate failed") for ln in lines), out
    assert f"REQUEUE {b.keys[3]}" in lines, out
    assert not any(b.keys[3] in ln for ln in lines if not ln.startswith("REQUEUE")), out
    assert [s.split(":")[0] for s in b.merges()] == [f"Merge {k}" for k in b.keys[:2]]
    assert 1 <= b.gate_runs() <= 1 + math.ceil(math.log2(4)), b.gate_runs()
    # the requeued ticket lands in the next pass
    r2 = b.run(stdin=b.lines[3])
    assert re.search(rf"^MERGED {b.keys[3]} [0-9a-f]{{40}}$", r2.stdout, re.M), r2.stdout + r2.stderr


def test_o14_max_two_builds_two_candidates_of_two_tickets_then_one(make):
    b = make()
    r = b.run(max_=2)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    builds = [keys_of(c) for c in b.calls("merge-candidate.sh") if "--remove" not in c]
    assert builds == [b.keys[:2], b.keys[2:3]], builds
    assert re.findall(r"^MERGED (\S+) ", r.stdout, re.M) == b.keys[:3], out


def test_o28_a_flaky_gate_requeues_the_whole_pass_without_bisecting(make):
    b = make(gate_override='echo "GATE FLAKE tests/test_x.py::test_flaky"; exit 1')
    r = b.run()
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    lines = r.stdout.splitlines()
    assert [ln for ln in lines if ln.startswith("REQUEUE ")] == [f"REQUEUE {k}" for k in b.keys[:3]], out
    assert "FLAKE tests/test_x.py::test_flaky" in lines, out
    assert len(b.calls("merge-gate.sh")) == 1, b.calls("merge-gate.sh")
    assert not any(ln.startswith(("MERGED", "REJECTED")) for ln in lines), out
    assert b.merges() == []
    assert git("rev-parse", "HEAD", cwd=b.epic) == b.epic_head
