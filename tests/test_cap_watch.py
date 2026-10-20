"""E3-T1 O6: cap-watch.sh kills the newest held run in role order when memory goes over the cap.

`cap-watch.sh <watch run id>` samples `PAD_MEMORY_PROBE` every `PAD_CAP_WATCH_INTERVAL` seconds
(default 2), writes its pid to `.work/runs/<id>/cap-watch.pid`, and while memory in use is above
the cap (host.md) kills one held run per sample: role agent, then suite-owner, then gate; within
a role the newest. Held runs are the ones `pad-proc.sh contain --run <id> --role <role> --`
started. A killed run's `contain` prints `CAP KILLED <run> at <GB>` and exits 75, and the line is
appended to the watch run's log (`.work/runs/<id>/progress.md`).
"""
from __future__ import annotations

import re
import subprocess
import time

import pytest

from conftest import BASH, BIN
from test_pad_proc import PROC, alive, clean_env, kill, posix, probe, wait_for, write_host

WATCH = (BIN / "cap-watch.sh").as_posix()


class Fleet:
    def __init__(self, repo, tmp_path, hot_run):
        """`hot_run`: memory reads 20 GB while that run's process lives, 1 GB otherwise."""
        self.repo, self.tmp = repo, tmp_path
        write_host(repo, total="16 GB", cap="10GB")
        pidfile = f"'{posix(tmp_path)}/{hot_run}.pid'"
        body = f'if kill -0 "$(cat {pidfile} 2>/dev/null)" 2>/dev/null; then echo 20; else echo 1; fi\n'
        self.env = clean_env(PAD_MEMORY_PROBE=probe(tmp_path, body), PAD_CAP_WATCH_INTERVAL="0.2")
        self.procs = []
        self.watcher = None

    def hold(self, run, role):
        d = posix(self.tmp)
        out = open(self.tmp / f"{run}.out", "w")
        p = subprocess.Popen(
            [BASH, PROC, "contain", "--run", run, "--role", role, "--", "bash", "-c",
             f"echo $$ > '{d}/{run}.pid'; exec sleep 300"],
            cwd=str(self.repo), env=self.env, stdout=out, stderr=subprocess.STDOUT)
        self.procs.append((p, out))
        assert wait_for(lambda: self.pid(run) is not None or p.poll() is not None)
        assert self.pid(run) is not None, f"{run} never started: {self.out(run)}"
        return p

    def pid(self, run):
        f = self.tmp / f"{run}.pid"
        text = f.read_text(encoding="utf-8").strip() if f.exists() else ""
        return text or None

    def out(self, run):
        return (self.tmp / f"{run}.out").read_text(encoding="utf-8", errors="replace")

    def watch(self, watch_id="w1"):
        self.watcher = subprocess.Popen([BASH, WATCH, watch_id], cwd=str(self.repo), env=self.env,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return self.watcher

    def finish(self):
        if self.watcher and self.watcher.poll() is None:
            self.watcher.kill()
            self.watcher.wait()
        for p, out in self.procs:
            if p.poll() is None:
                p.kill()
            p.wait()
            out.close()
        for run in {p.name[:-4] for p in self.tmp.glob("*.pid")}:
            pid = self.pid(run)
            if pid:
                kill(pid)


@pytest.fixture
def fleet(repo, tmp_path):
    made = []

    def make(hot_run):
        f = Fleet(repo, tmp_path, hot_run)
        made.append(f)
        return f

    yield make
    for f in made:
        f.finish()


def test_o6_the_agent_run_is_killed_first_even_when_a_gate_run_is_newer(fleet):
    f = fleet("agent1")
    agent = f.hold("agent1", "agent")
    f.hold("owner1", "suite-owner")
    gate = f.hold("gate1", "gate")
    f.watch()
    assert agent.wait(timeout=60) == 75, f.out("agent1")
    assert alive(f.pid("owner1")) and alive(f.pid("gate1")) and gate.poll() is None


def test_o6_the_suite_owner_run_is_killed_before_a_gate_run(fleet):
    f = fleet("owner1")
    owner = f.hold("owner1", "suite-owner")
    gate = f.hold("gate1", "gate")
    f.watch()
    assert owner.wait(timeout=60) == 75, f.out("owner1")
    assert alive(f.pid("gate1")) and gate.poll() is None


def test_o6_within_a_role_the_newest_run_is_killed(fleet):
    f = fleet("agent2")
    older = f.hold("agent1", "agent")
    newer = f.hold("agent2", "agent")
    f.watch()
    assert newer.wait(timeout=60) == 75, f.out("agent2")
    assert alive(f.pid("agent1")) and older.poll() is None


def test_o6_a_killed_run_says_cap_killed_with_the_memory_it_was_killed_at(fleet):
    f = fleet("agent1")
    agent = f.hold("agent1", "agent")
    f.watch()
    assert agent.wait(timeout=60) == 75
    assert re.search(r"CAP KILLED agent1 at 20(?:\.0+)?\b", f.out("agent1")), f.out("agent1")


def test_o6_the_kill_is_appended_to_the_run_log(fleet, repo):
    f = fleet("agent1")
    agent = f.hold("agent1", "agent")
    f.watch("w1")
    assert agent.wait(timeout=60) == 75
    log = repo / ".work" / "runs" / "w1" / "progress.md"
    assert wait_for(lambda: log.exists() and "CAP KILLED agent1" in log.read_text(encoding="utf-8"))
    assert re.search(r"CAP KILLED agent1 at 20", log.read_text(encoding="utf-8"))


def test_o6_nothing_is_killed_while_memory_is_within_the_cap(fleet, tmp_path):
    f = fleet("nobody")  # never started: memory reads 1 GB throughout
    agent = f.hold("agent1", "agent")
    counter = tmp_path / "samples"
    f.env["PAD_MEMORY_PROBE"] = probe(
        tmp_path, f"echo x >> '{posix(counter)}'; echo 9\n", name="counting.sh")
    f.watch()
    assert wait_for(lambda: counter.exists() and len(counter.read_text().split()) >= 4)
    time.sleep(0.3)
    assert agent.poll() is None and alive(f.pid("agent1"))


def test_o6_the_watchdog_records_its_pid_for_the_heartbeat(fleet, repo):
    f = fleet("nobody")
    w = f.watch("w9")
    pidfile = repo / ".work" / "runs" / "w9" / "cap-watch.pid"
    assert wait_for(lambda: pidfile.exists() and pidfile.read_text().strip() != "")
    assert w.poll() is None
