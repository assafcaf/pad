"""E3-T9 L1, L2: the session-end leak check finds processes by inheritance from the session.

L1  a process a test started and did not stop is found whatever its command line says (no
    `payload/`, no temp path in it): the run fails with `LEAK <pid> <command>` and the process is
    gone afterwards.
L2  a process another session or program started (not inherited from this session) is neither
    reported nor killed.

Each runs an inner pytest session in a subprocess (pytester) with this repo's tests/conftest.py.
"""
from __future__ import annotations

import subprocess

import pytest

from conftest import BASH, kill_tree
from test_fast_budget import with_repo_conftest
from test_pad_proc import alive, wait_for

pytest_plugins = ["pytester"]

LEAKER = '''
import os, subprocess, time

def test_leaker():
    subprocess.Popen([r"{bash}", "-c", "echo $$ > '{pidfile}'; exec sleep 600"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end = time.monotonic() + 60
    while time.monotonic() < end and not (os.path.exists(r"{pidfile}")
                                          and open(r"{pidfile}").read().strip()):
        time.sleep(0.05)
'''


@pytest.mark.slow
def test_l1_a_process_with_no_path_in_its_command_line_is_reported_and_killed(pytester):
    with_repo_conftest(pytester)
    pidfile = pytester.path / "leaker.pid"
    pytester.makepyfile(test_inner=LEAKER.format(bash=BASH, pidfile=pidfile.as_posix()))
    result = pytester.runpytest_subprocess()
    pid = pidfile.read_text().strip() if pidfile.exists() else ""
    try:
        out = "\n".join(result.stdout.lines)
        assert result.ret != 0, out
        leaks = [ln for ln in result.stdout.lines if ln.startswith("LEAK ")]
        assert any("sleep 600" in ln for ln in leaks), out
        assert pid.isdigit(), "the leaker never recorded its pid"
        assert wait_for(lambda: not alive(pid)), "the leaked process was not killed"
    finally:
        if pid.isdigit():
            kill_tree(int(pid))


@pytest.mark.slow
def test_l2_a_process_this_session_did_not_start_is_left_alone(pytester):
    other = subprocess.Popen([BASH, "-c", "echo $$; exec sleep 603"],
                             stdout=subprocess.PIPE, text=True)
    pid = other.stdout.readline().strip()
    try:
        assert wait_for(lambda: alive(pid)), "the bystander never started"
        with_repo_conftest(pytester)
        pytester.makepyfile(test_inner="def test_trivial():\n    pass\n")
        result = pytester.runpytest_subprocess()
        assert result.ret == 0, "\n".join(result.stdout.lines)
        assert not [ln for ln in result.stdout.lines if ln.startswith("LEAK ")]
        assert alive(pid), "the session killed a process it did not start"
    finally:
        if pid.isdigit():
            kill_tree(int(pid))
        other.kill()
        other.wait(timeout=30)
        other.stdout.close()
