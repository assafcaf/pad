"""E3-T1: pad-proc.sh, the host library behind every contained test run (O5, O6, O8 pieces).

`pad-proc.sh <verb> ...` is both sourceable and runnable; the tests run it.
  mem-in-use            machine memory in use, in GB, from the probe: `PAD_MEMORY_PROBE` (a shell
                        command printing a number), else the OS's own. Exit 2 with a reason on
                        stderr when the probe fails (never a silent uncapped run).
  cap                   the cap in GB: `Memory cap:` of host.md (`<n>%` of `Memory total:`, or
                        `<n>GB`); with no host.md 85% of `PAD_MEMORY_TOTAL_GB` (else the machine).
  contain --run <id> --role <role> -- <cmd...>
                        runs cmd contained, recorded under .work/runs/<id>/pad-test/, exits with
                        cmd's code; when the watchdog killed it, prints `CAP KILLED <id> at <GB>`
                        and exits 75.
  sweep                 kills processes recorded under finished runs: a run's record is
                        `.work/runs/<id>/pad-test/<name>.pids` (one pid per line), finished once
                        `<name>.done` exists beside it. Prints `SWEPT <n> processes, <GB>`.
host.md is `<repo>/.claude/workflow/host.md`, or `PAD_HOST_MD`.
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

import pytest

from conftest import BASH, BIN

PROC = (BIN / "pad-proc.sh").as_posix()


def posix(p: Path) -> str:
    return p.as_posix()


def wait_for(pred, timeout: float = 40.0, step: float = 0.1) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(step)
    return bool(pred())


def clean_env(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("PAD_MEMORY", "PAD_HOST", "PAD_SUITE", "PAD_CAP", "PAD_CORES"))}
    env.update(extra)
    return env


def write_host(repo: Path, total: str = "16 GB", cap: str = "85%") -> Path:
    path = repo / ".claude" / "workflow" / "host.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"OS: test\nMemory total: {total}\nMemory cap: {cap}\nSelf-test: ok\n", encoding="utf-8")
    return path


def probe(tmp: Path, body: str, name: str = "probe.sh") -> str:
    """A fake memory probe: a bash script; returns the PAD_MEMORY_PROBE command for it."""
    script = tmp / name
    script.write_text(body, encoding="utf-8", newline="\n")
    return f"bash '{posix(script)}'"


def run_proc(repo: Path, env: dict[str, str], *args: str, timeout: float = 120):
    return subprocess.run([BASH, PROC, *args], cwd=str(repo), env=env, capture_output=True,
                          text=True, timeout=timeout)


def alive(pid: str) -> bool:
    return subprocess.run([BASH, "-c", f"kill -0 {int(pid)}"], capture_output=True).returncode == 0


def kill(pid: str) -> None:
    subprocess.run([BASH, "-c", f"kill -9 {int(pid)} 2>/dev/null; true"], capture_output=True)


def num(text: str) -> float:
    m = re.search(r"[0-9]+(?:\.[0-9]+)?", text)
    assert m, text
    return float(m.group(0))


# --- memory in use and the cap -------------------------------------------------------------

def test_mem_in_use_reports_what_the_probe_prints(repo, tmp_path):
    env = clean_env(PAD_MEMORY_PROBE=probe(tmp_path, "echo 7.5\n"))
    r = run_proc(repo, env, "mem-in-use")
    assert r.returncode == 0, r.stderr
    assert num(r.stdout) == 7.5


def test_a_failing_memory_probe_is_exit_2_with_a_reason_never_silence(repo, tmp_path):
    env = clean_env(PAD_MEMORY_PROBE=probe(tmp_path, "echo no counter >&2\nexit 3\n"))
    r = run_proc(repo, env, "mem-in-use")
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert r.stderr.strip() != ""


def test_a_percentage_cap_is_that_share_of_total_memory(repo):
    write_host(repo, total="16 GB", cap="50%")
    r = run_proc(repo, clean_env(), "cap")
    assert r.returncode == 0, r.stderr
    assert num(r.stdout) == 8.0


def test_a_gb_cap_is_taken_as_given(repo):
    write_host(repo, total="16 GB", cap="6GB")
    r = run_proc(repo, clean_env(), "cap")
    assert r.returncode == 0, r.stderr
    assert num(r.stdout) == 6.0


def test_with_no_host_md_the_cap_is_85_percent_of_total(repo):
    r = run_proc(repo, clean_env(PAD_MEMORY_TOTAL_GB="20"), "cap")
    assert r.returncode == 0, r.stderr
    assert num(r.stdout) == pytest.approx(17.0)


# --- O8: the sweep ---------------------------------------------------------------------------

def leftover() -> str:
    """A detached process that outlives its starter; returns its pid (as bash sees it)."""
    r = subprocess.run([BASH, "-c", "nohup sleep 300 >/dev/null 2>&1 </dev/null & echo $!"],
                       capture_output=True, text=True, timeout=60)
    pid = r.stdout.strip().splitlines()[-1]
    assert pid.isdigit(), r
    return pid


def record(repo: Path, run: str, pid: str, done: bool) -> None:
    d = repo / ".work" / "runs" / run / "pad-test"
    d.mkdir(parents=True, exist_ok=True)
    (d / "slot1.pids").write_text(f"{pid}\n", encoding="utf-8", newline="\n")
    if done:
        (d / "slot1.done").write_text("0\n", encoding="utf-8")


def test_o8_sweep_kills_a_process_left_under_a_finished_run_and_reports_it(repo):
    pid = leftover()
    try:
        record(repo, "run-ended", pid, done=True)
        r = run_proc(repo, clean_env(), "sweep")
        assert r.returncode == 0, r.stderr
        assert re.search(r"^SWEPT 1 processes, ", r.stdout + r.stderr, re.M), (r.stdout, r.stderr)
        assert wait_for(lambda: not alive(pid)), "the leftover process survived the sweep"
    finally:
        kill(pid)


def test_o8_sweep_leaves_a_process_of_a_run_that_has_not_ended(repo):
    pid = leftover()
    try:
        record(repo, "run-live", pid, done=False)
        r = run_proc(repo, clean_env(), "sweep")
        assert r.returncode == 0, r.stderr
        assert not re.search(r"^SWEPT [1-9]", r.stdout + r.stderr, re.M), (r.stdout, r.stderr)
        assert alive(pid), "the sweep killed a live run's process"
    finally:
        kill(pid)


def test_o8_sweep_counts_only_processes_it_killed(repo):
    gone = leftover()
    kill(gone)
    wait_for(lambda: not alive(gone))
    pid = leftover()
    try:
        record(repo, "run-a", gone, done=True)
        record(repo, "run-b", pid, done=True)
        r = run_proc(repo, clean_env(), "sweep")
        assert re.search(r"^SWEPT 1 processes, ", r.stdout + r.stderr, re.M), (r.stdout, r.stderr)
        assert wait_for(lambda: not alive(pid))
    finally:
        kill(pid)
