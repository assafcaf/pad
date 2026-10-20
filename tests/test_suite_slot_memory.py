"""E3-T1: suite-slot.sh admits a run against the memory cap and the cores (O5, O7).

`suite-slot.sh [--estimate-gb <n>] [--workers <n>] -- <cmd...>`: giving either turns admission
on (a bare run keeps today's behaviour). Admission holds the run until machine memory in use
(`PAD_MEMORY_PROBE`, GB) plus the estimate is within the cap (host.md), and until the held runs'
workers plus its own are within `PAD_CORES` x the cap's share of total memory. While it waits it
prints `CAP WAIT <in use>/<cap>` on stderr, first at once and then every `PAD_CAP_WAIT_INTERVAL`
seconds (default 60); it re-checks at least every 2 s. An estimate above the whole cap starts
only when no other run holds a slot.
"""
from __future__ import annotations

import re
import subprocess
import time

import pytest

from conftest import BASH, BIN
from test_pad_proc import clean_env, posix, probe, wait_for, write_host

SLOT = (BIN / "suite-slot.sh").as_posix()


class Runs:
    def __init__(self, repo, tmp_path, **env):
        self.repo, self.tmp = repo, tmp_path
        self.env = clean_env(PAD_SUITE_SLOTS="4", PAD_HOST_SLOTS_DIR=posix(tmp_path / "hostslots"),
                             PAD_CAP_WAIT_INTERVAL="1000", **env)
        self.procs = []

    def start(self, name, *flags, hold=False):
        """Run `suite-slot.sh <flags> -- <cmd>`; cmd touches <name>.in, and when hold waits for <name>.go."""
        d = posix(self.tmp)
        body = f"touch '{d}/{name}.in'"
        if hold:
            body += f"; while [ ! -f '{d}/{name}.go' ]; do sleep 0.1; done"
        err = open(self.tmp / f"{name}.err", "w")
        p = subprocess.Popen([BASH, SLOT, *flags, "--", "bash", "-c", body], cwd=str(self.repo),
                             env=self.env, stdout=subprocess.DEVNULL, stderr=err)
        self.procs.append((p, err))
        return p

    def inside(self, name):
        return (self.tmp / f"{name}.in").exists()

    def release(self, name):
        (self.tmp / f"{name}.go").write_text("go", encoding="utf-8")

    def err(self, name):
        return (self.tmp / f"{name}.err").read_text(encoding="utf-8", errors="replace")

    def finish(self):
        for p, err in self.procs:
            if p.poll() is None:
                p.kill()
            p.wait()
            err.close()


@pytest.fixture
def runs(repo, tmp_path):
    made = []

    def make(cap="10GB", total="16 GB", used="8", cores=None):
        write_host(repo, total=total, cap=cap)
        extra = {"PAD_MEMORY_PROBE": probe(tmp_path, f"cat '{posix(tmp_path)}/used'\n")}
        if cores:
            extra["PAD_CORES"] = cores
        (tmp_path / "used").write_text(used, encoding="utf-8")
        r = Runs(repo, tmp_path, **extra)
        made.append(r)
        return r

    yield make
    for r in made:
        r.finish()


def cap_wait(used: int, cap: int) -> str:
    return rf"CAP WAIT {used}(?:\.0+)?/{cap}(?:\.0+)?"


def test_o5_a_run_that_does_not_fit_waits_prints_cap_wait_and_starts_when_it_fits(runs, tmp_path):
    r = runs(cap="10GB", used="8")
    p = r.start("a", "--estimate-gb", "4")
    assert wait_for(lambda: re.search(cap_wait(8, 10), r.err("a"))), r.err("a")
    assert not r.inside("a"), "started although 8 + 4 GB is above the 10 GB cap"
    (tmp_path / "used").write_text("1", encoding="utf-8")
    assert wait_for(lambda: r.inside("a")), r.err("a")
    assert p.wait(timeout=30) == 0


def test_o5_an_estimate_that_exactly_fills_the_cap_starts_at_once(runs):
    r = runs(cap="10GB", used="6")
    p = r.start("a", "--estimate-gb", "4")
    assert p.wait(timeout=60) == 0, r.err("a")
    assert r.inside("a")
    assert "CAP WAIT" not in r.err("a")


def test_o5_cap_wait_is_printed_once_per_interval_not_once_per_check(runs):
    r = runs(cap="10GB", used="9")
    r.start("a", "--estimate-gb", "4")
    assert wait_for(lambda: "CAP WAIT" in r.err("a")), r.err("a")
    for _ in range(8):
        time.sleep(0.3)
    assert r.err("a").count("CAP WAIT") == 1, r.err("a")


def test_o5_an_estimate_above_the_whole_cap_waits_while_another_run_is_held(runs):
    r = runs(cap="10GB", used="1")
    r.start("a", "--estimate-gb", "1", hold=True)
    assert wait_for(lambda: r.inside("a"))
    big = r.start("big", "--estimate-gb", "12")
    assert wait_for(lambda: "CAP WAIT" in r.err("big")), r.err("big")
    assert not r.inside("big"), "a 12 GB run started beside another held run under a 10 GB cap"
    r.release("a")
    assert wait_for(lambda: r.inside("big")), r.err("big")
    assert big.wait(timeout=30) == 0


def test_o5_an_estimate_above_the_whole_cap_starts_when_no_other_run_is_held(runs):
    r = runs(cap="10GB", used="1")
    big = r.start("big", "--estimate-gb", "12")
    assert big.wait(timeout=60) == 0, r.err("big")
    assert r.inside("big")


def test_o5_an_unavailable_memory_probe_refuses_with_exit_2_and_runs_nothing(repo, tmp_path):
    write_host(repo, cap="10GB")
    env = clean_env(PAD_SUITE_SLOTS="2", PAD_HOST_SLOTS_DIR=posix(tmp_path / "hostslots"),
                    PAD_MEMORY_PROBE=probe(tmp_path, "echo no counter >&2\nexit 3\n"))
    r = subprocess.run([BASH, SLOT, "--estimate-gb", "1", "--", "bash", "-c",
                        f"touch '{posix(tmp_path)}/ran'"],
                       cwd=str(repo), env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert r.stderr.strip() != ""
    assert not (tmp_path / "ran").exists()


def test_o7_workers_that_would_exceed_cores_times_the_cap_share_wait(runs):
    # 4 cores x 50% cap share = 2 workers; memory is not the constraint (8 GB cap, 1 in use).
    r = runs(cap="50%", total="16 GB", used="1", cores="4")
    r.start("a", "--estimate-gb", "1", "--workers", "2", hold=True)
    assert wait_for(lambda: r.inside("a"))
    b = r.start("b", "--estimate-gb", "1", "--workers", "1")
    assert wait_for(lambda: "CAP WAIT" in r.err("b")), r.err("b")
    assert not r.inside("b"), "3 workers were admitted on a 2 worker budget"
    r.release("a")
    assert wait_for(lambda: r.inside("b")), r.err("b")
    assert b.wait(timeout=30) == 0


def test_o7_workers_within_the_budget_run_side_by_side(runs):
    r = runs(cap="50%", total="16 GB", used="1", cores="4")
    r.start("a", "--estimate-gb", "1", "--workers", "1", hold=True)
    assert wait_for(lambda: r.inside("a"))
    b = r.start("b", "--estimate-gb", "1", "--workers", "1")
    assert b.wait(timeout=60) == 0, r.err("b")
    assert r.inside("b") and "CAP WAIT" not in r.err("b")
    r.release("a")
