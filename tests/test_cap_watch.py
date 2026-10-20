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

from conftest import BASH, BIN, kill_tree
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
        # the launcher is gone; the real bash it started (the watchdog, each contained run's
        # host) is not: stop each by tree
        mains = [self.repo / ".work" / "runs"]
        for f in list(mains[0].glob("*/cap-watch.pid")) + list(mains[0].glob("*/pad-test/*.meta")):
            text = f.read_text(encoding="utf-8").strip()
            pid = text if f.suffix == ".pid" else next(
                (ln[5:] for ln in text.splitlines() if ln.startswith("host=")), "")
            if pid.isdigit():
                kill_tree(int(pid))
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


@pytest.mark.slow
def test_o6_the_agent_run_is_killed_first_even_when_a_gate_run_is_newer(fleet):
    f = fleet("agent1")
    agent = f.hold("agent1", "agent")
    f.hold("owner1", "suite-owner")
    gate = f.hold("gate1", "gate")
    f.watch()
    assert agent.wait(timeout=60) == 75, f.out("agent1")
    assert alive(f.pid("owner1")) and alive(f.pid("gate1")) and gate.poll() is None


@pytest.mark.slow
def test_o6_the_suite_owner_run_is_killed_before_a_gate_run(fleet):
    f = fleet("owner1")
    owner = f.hold("owner1", "suite-owner")
    gate = f.hold("gate1", "gate")
    f.watch()
    assert owner.wait(timeout=60) == 75, f.out("owner1")
    assert alive(f.pid("gate1")) and gate.poll() is None


@pytest.mark.slow
def test_o6_within_a_role_the_newest_run_is_killed(fleet):
    f = fleet("agent2")
    older = f.hold("agent1", "agent")
    newer = f.hold("agent2", "agent")
    f.watch()
    assert newer.wait(timeout=60) == 75, f.out("agent2")
    assert alive(f.pid("agent1")) and older.poll() is None


@pytest.mark.slow
def test_o6_a_killed_run_says_cap_killed_with_the_memory_it_was_killed_at(fleet):
    f = fleet("agent1")
    agent = f.hold("agent1", "agent")
    f.watch()
    assert agent.wait(timeout=60) == 75
    assert re.search(r"CAP KILLED agent1 at 20(?:\.0+)?\b", f.out("agent1")), f.out("agent1")


@pytest.mark.slow
def test_o6_the_kill_is_appended_to_the_run_log(fleet, repo):
    f = fleet("agent1")
    agent = f.hold("agent1", "agent")
    f.watch("w1")
    assert agent.wait(timeout=60) == 75
    log = repo / ".work" / "runs" / "w1" / "progress.md"
    assert wait_for(lambda: log.exists() and "CAP KILLED agent1" in log.read_text(encoding="utf-8"))
    assert re.search(r"CAP KILLED agent1 at 20", log.read_text(encoding="utf-8"))


@pytest.mark.slow
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


# --- R1: one check costs a bounded number of processes -----------------------------------------

from pathlib import Path as _Path  # noqa: E402

from test_pad_proc import calls, counting_shims, real_bash, shimmed  # noqa: E402


def _sleepers(tmp: _Path, n: int = 3) -> list[str]:
    """n live processes (pids as bash sees them), standing in for a run's recorded tree."""
    f = tmp / "sleepers.pids"
    f.write_text("", encoding="utf-8")
    subprocess.Popen(
        [BASH, "-c", f"for i in $(seq 1 {n}); do sleep 300 & echo $! >> '{posix(f)}'; done; wait"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert wait_for(lambda: len(f.read_text().split()) >= n)
    return f.read_text().split()


def _record(repo, run, name, role, start, pids, extra=()):
    d = repo / ".work" / "runs" / run / "pad-test"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.meta").write_text(
        f"run={run}\nrole={role}\nstart={start}\nhost=1\n", encoding="utf-8", newline="\n")
    (d / f"{name}.pids").write_text("".join(f"{p}\n" for p in pids), encoding="utf-8", newline="\n")
    for ext in extra:
        (d / f"{name}.{ext}").write_text("0\n", encoding="utf-8")


def _one_check(repo, tmp_path, records: int, tag: str):
    """One over-cap check of cap-watch.sh against `records` held runs; returns the call log."""
    t = tmp_path / tag
    t.mkdir()
    write_host(repo, total="16 GB", cap="10GB")
    pids = _sleepers(t)
    for i in range(records):
        _record(repo, f"{tag}{i}", f"{tag}{i}", "agent", 1000 + i, pids)
    shims, log = counting_shims(
        t, ("ps", "powershell.exe", "sed", "head", "tr", "cat", "awk", "sort", "date"))
    env = shimmed(clean_env(PAD_MEMORY_PROBE=probe(t, "echo 20\n"),
                            PAD_CAP_WATCH_INTERVAL="600"), shims)
    w = subprocess.Popen([real_bash(), WATCH, tag], cwd=str(repo), env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    progress = repo / ".work" / "runs" / tag / "progress.md"
    try:
        assert wait_for(
            lambda: progress.exists() and "CAP KILLED" in progress.read_text(encoding="utf-8")
        ), "the check never killed a run"
    finally:
        pf = repo / ".work" / "runs" / tag / "cap-watch.pid"
        if pf.exists() and pf.read_text().strip().isdigit():
            kill_tree(int(pf.read_text().strip()))  # the watcher's own `sleep` goes with it
        w.kill()
        w.wait()
        for p in pids:
            kill(p)
    return calls(log)


@pytest.mark.slow
def test_r1_one_check_lists_processes_once_and_starts_no_powershell(repo, tmp_path):
    made = _one_check(repo, tmp_path, 8, "many")
    assert [n for n, _ in made if n.startswith("powershell")] == []
    assert len([n for n, _ in made if n == "ps"]) <= 1, made


@pytest.mark.slow
def test_r1_the_processes_a_check_starts_do_not_grow_with_the_number_of_records(repo, tmp_path):
    few = _one_check(repo, tmp_path, 2, "few")
    many = _one_check(repo, tmp_path, 8, "many")
    assert len(many) <= len(few), f"2 records: {len(few)} starts, 8 records: {len(many)}"


# --- R3: the victim choice, asked for directly -------------------------------------------------

def _victim(repo) -> str:
    r = subprocess.run([BASH, PROC, "victim"], cwd=str(repo), env=clean_env(),
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, (r.stdout, r.stderr)
    return r.stdout.strip()


@pytest.fixture
def live(tmp_path):
    pids = _sleepers(tmp_path, 1)
    yield pids
    for p in pids:
        kill(p)


def test_r3_the_victim_is_the_agent_run_even_when_a_gate_run_is_newer(repo, live):
    _record(repo, "ra", "agent-a", "agent", 100, live)
    _record(repo, "rs", "owner-s", "suite-owner", 200, live)
    _record(repo, "rg", "gate-g", "gate", 300, live)
    assert _victim(repo) == "agent-a"


def test_r3_the_victim_is_the_suite_owner_run_before_a_gate_run(repo, live):
    _record(repo, "rs", "owner-s", "suite-owner", 100, live)
    _record(repo, "rg", "gate-g", "gate", 300, live)
    assert _victim(repo) == "owner-s"


def test_r3_within_a_role_the_victim_is_the_newest_run(repo, live):
    _record(repo, "r1", "agent-old", "agent", 100, live)
    _record(repo, "r2", "agent-new", "agent", 500, live)
    _record(repo, "r3", "agent-mid", "agent", 300, live)
    assert _victim(repo) == "agent-new"


def test_r3_a_finished_killed_or_dead_run_and_an_operator_run_are_never_the_victim(repo, live):
    gone = subprocess.run([BASH, "-c", "echo $$"], capture_output=True, text=True).stdout.strip()
    _record(repo, "r1", "agent-done", "agent", 900, live, extra=("done",))
    _record(repo, "r2", "agent-killed", "agent", 800, live, extra=("killed",))
    _record(repo, "r3", "agent-dead", "agent", 700, [gone])
    _record(repo, "r4", "operator-x", "operator", 600, live)
    _record(repo, "r5", "gate-g", "gate", 100, live)
    assert _victim(repo) == "gate-g"


def test_r3_with_nothing_killable_the_victim_is_empty_and_nothing_is_killed(repo, live):
    _record(repo, "r4", "operator-x", "operator", 600, live)
    assert _victim(repo) == ""
    assert alive(live[0])


# --- R7: a watchdog does not outlive its starter -----------------------------------------------

def _wrapper(tmp: _Path, repo, script: str, args: str, env):
    """Start `bash <script> <args>` in the background of a wrapper bash; returns (handle,
    wrapper pid, script pid), the pids as bash sees them."""
    wp, sp = tmp / "wrapper.pid", tmp / "script.pid"
    p = subprocess.Popen(
        [BASH, "-c", f"bash {script} {args} & echo $! > '{posix(sp)}'; echo $$ > '{posix(wp)}'; wait"],
        cwd=str(repo), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert wait_for(lambda: wp.exists() and sp.exists()
                    and wp.read_text().strip() != "" and sp.read_text().strip() != "")
    return p, wp.read_text().strip(), sp.read_text().strip()


@pytest.mark.slow
def test_r7_cap_watch_exits_when_the_process_that_started_it_is_gone(repo, tmp_path):
    write_host(repo, total="16 GB", cap="10GB")
    env = clean_env(PAD_MEMORY_PROBE=probe(tmp_path, "echo 1\n"), PAD_CAP_WATCH_INTERVAL="0.2")
    p, wrapper, script = _wrapper(tmp_path, repo, WATCH, "w7", env)
    try:
        assert alive(script)
        kill(wrapper)
        assert wait_for(lambda: not alive(script)), "cap-watch.sh outlived its starter"
    finally:
        kill(script)
        kill(wrapper)
        p.kill()
        p.wait()


@pytest.mark.slow
def test_r7_cap_watch_exits_when_its_pid_file_is_removed(repo, tmp_path):
    write_host(repo, total="16 GB", cap="10GB")
    env = clean_env(PAD_MEMORY_PROBE=probe(tmp_path, "echo 1\n"), PAD_CAP_WATCH_INTERVAL="0.2")
    w = subprocess.Popen([BASH, WATCH, "w8"], cwd=str(repo), env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pidfile = repo / ".work" / "runs" / "w8" / "cap-watch.pid"
    try:
        assert wait_for(lambda: pidfile.exists() and pidfile.read_text().strip() != "")
        pid = pidfile.read_text().strip()
        pidfile.unlink()
        assert wait_for(lambda: not alive(pid)), "cap-watch.sh kept running without its pid file"
    finally:
        if pidfile.exists():
            kill(pidfile.read_text().strip())
        w.kill()
        w.wait()
