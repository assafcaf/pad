"""E3-T2 O41, O42, O9: the pytest runner adapter, runners/pytest.sh.

    pytest.sh run <report-dir> (--tier-arg <arg> | --ids <id>...) [--workers n] [--kill-per-test s] [--shuffle]
    pytest.sh results <report-dir>     lines `pass|failure|error|skipped <id> [<message>]`, ids `<file>::<test>`
    pytest.sh runner-names | protected-files | acceptance-pattern <KEY> | capabilities

Run in the project's directory. `PAD_TIER=fast` in the environment makes the fast-tier contract
apply (the adapter declares `contract-fast`): a test that opens a socket or starts a subprocess
fails at the call. The adapter declares `leak-check`: a process the run started that is still
alive when it ends fails the run with `LEAK <pid> <command>`. These tests need python with pytest
on the PATH as `python` or `python3`.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

from conftest import BASH, BIN

ADAPTER = (BIN.parent / "runners" / "pytest.sh").as_posix()

BASIC = '''\
import unittest

def test_ok():
    assert 1 + 1 == 2

def test_bad():
    assert 1 + 1 == 3, "arithmetic broke"

def test_skipped():
    raise unittest.SkipTest("not today")
'''

BROKEN = "import module_that_does_not_exist\n\ndef test_never():\n    pass\n"

NET = '''\
import socket

def test_opens_a_socket():
    s = socket.socket()
    s.close()
'''

PROC = '''\
import subprocess, sys

def test_starts_a_subprocess():
    subprocess.run([sys.executable, "-c", "pass"], check=True)

def test_plain():
    assert True
'''

LEAK = '''\
import os, subprocess, sys

def test_leaves_a_child_running():
    p = subprocess.Popen([sys.executable, "-c", "import threading; threading.Event().wait()"])
    with open(os.environ["LEAK_PIDFILE"], "w") as f:
        f.write(str(p.pid))
'''


@pytest.fixture
def proj(tmp_path):
    d = tmp_path / "proj"
    (d / "tests" / "fast").mkdir(parents=True)
    (d / "tests" / "heavy").mkdir(parents=True)
    (d / "tests" / "fast" / "test_basic.py").write_text(BASIC, encoding="utf-8")
    return d


def adapter(proj: Path, *args: str, tier: str = "", extra: dict | None = None, timeout: float = 170):
    env = {k: v for k, v in os.environ.items() if k != "PAD_TIER"}
    if tier:
        env["PAD_TIER"] = tier
    env.update(extra or {})
    return subprocess.run([BASH, ADAPTER, *args], cwd=str(proj), env=env, capture_output=True,
                          text=True, encoding="utf-8", timeout=timeout)


def results(proj: Path, report: Path) -> dict[str, str]:
    r = adapter(proj, "results", report.as_posix())
    assert r.returncode == 0, r.stderr
    got = {}
    for line in r.stdout.splitlines():
        kind, ident, *_ = line.split(" ", 2)
        assert kind in {"pass", "failure", "error", "skipped"}, line
        got[ident] = kind
    return got


# --- the verbs -------------------------------------------------------------------------------

def test_the_adapter_names_its_runner_surface_and_capabilities(proj):
    names = adapter(proj, "runner-names")
    assert names.returncode == 0 and "pytest" in names.stdout
    prot = adapter(proj, "protected-files")
    assert prot.returncode == 0 and "conftest.py" in prot.stdout
    acc = adapter(proj, "acceptance-pattern", "E3-T2")
    assert acc.returncode == 0 and "E3-T2" in acc.stdout and ".py" in acc.stdout
    caps = adapter(proj, "capabilities").stdout.split()
    assert {"contract-fast", "leak-check", "shuffle"} <= set(caps), caps


# --- run and results -------------------------------------------------------------------------

@pytest.mark.slow
def test_run_reports_pass_failure_and_skipped_by_id(proj, tmp_path):
    report = tmp_path / "report"
    r = adapter(proj, "run", report.as_posix(), "--tier-arg", "tests/fast")
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert results(proj, report) == {
        "tests/fast/test_basic.py::test_ok": "pass",
        "tests/fast/test_basic.py::test_bad": "failure",
        "tests/fast/test_basic.py::test_skipped": "skipped",
    }
    msgs = adapter(proj, "results", report.as_posix()).stdout
    assert re.search(r"^failure tests/fast/test_basic.py::test_bad .*arithmetic broke", msgs, re.M), msgs


@pytest.mark.slow
def test_run_by_ids_runs_only_those(proj, tmp_path):
    report = tmp_path / "report"
    r = adapter(proj, "run", report.as_posix(), "--ids", "tests/fast/test_basic.py::test_ok")
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert results(proj, report) == {"tests/fast/test_basic.py::test_ok": "pass"}


@pytest.mark.slow
def test_a_file_that_cannot_be_collected_is_an_error_not_a_failure(proj, tmp_path):
    (proj / "tests" / "fast" / "test_broken.py").write_text(BROKEN, encoding="utf-8")
    report = tmp_path / "report"
    r = adapter(proj, "run", report.as_posix(), "--tier-arg", "tests/fast/test_broken.py")
    assert r.returncode != 0
    got = results(proj, report)
    assert got and set(got.values()) == {"error"}, got
    assert all("test_broken.py" in k for k in got), got


@pytest.mark.slow
def test_shuffle_changes_the_order_but_not_the_set(proj, tmp_path):
    body = "".join(f"def test_{c}():\n    open('order.txt', 'a').write('{c}')\n\n" for c in "abcdefgh")
    (proj / "tests" / "fast" / "test_order.py").write_text(body, encoding="utf-8")
    orders = set()
    for i in range(6):
        (proj / "order.txt").unlink(missing_ok=True)
        r = adapter(proj, "run", (tmp_path / f"r{i}").as_posix(), "--tier-arg", "tests/fast/test_order.py", "--shuffle")
        assert r.returncode == 0, (r.stdout, r.stderr)
        got = (proj / "order.txt").read_text()
        assert sorted(got) == list("abcdefgh")
        orders.add(got)
    assert len(orders) > 1 or "abcdefgh" not in orders, orders


# --- O41: the fast-tier contract -------------------------------------------------------------

@pytest.mark.slow
def test_o41_in_the_fast_tier_a_test_that_opens_a_socket_fails_at_the_call(proj, tmp_path):
    (proj / "tests" / "fast" / "test_net.py").write_text(NET, encoding="utf-8")
    report = tmp_path / "report"
    r = adapter(proj, "run", report.as_posix(), "--tier-arg", "tests/fast/test_net.py", tier="fast")
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert results(proj, report) == {"tests/fast/test_net.py::test_opens_a_socket": "failure"}


@pytest.mark.slow
def test_o41_in_the_fast_tier_a_test_that_starts_a_subprocess_fails_at_the_call(proj, tmp_path):
    (proj / "tests" / "fast" / "test_proc.py").write_text(PROC, encoding="utf-8")
    report = tmp_path / "report"
    r = adapter(proj, "run", report.as_posix(), "--tier-arg", "tests/fast/test_proc.py", tier="fast")
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert results(proj, report) == {
        "tests/fast/test_proc.py::test_starts_a_subprocess": "failure",
        "tests/fast/test_proc.py::test_plain": "pass",
    }


@pytest.mark.slow
def test_o41_outside_the_fast_tier_the_same_tests_pass(proj, tmp_path):
    (proj / "tests" / "heavy" / "test_net.py").write_text(NET, encoding="utf-8")
    (proj / "tests" / "heavy" / "test_proc.py").write_text(PROC, encoding="utf-8")
    report = tmp_path / "report"
    r = adapter(proj, "run", report.as_posix(), "--tier-arg", "tests/heavy", tier="heavy")
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert set(results(proj, report).values()) == {"pass"}


# --- O42: leak check -------------------------------------------------------------------------

def _stop(pidfile: Path) -> None:
    if pidfile.is_file():
        try:
            os.kill(int(pidfile.read_text().strip()), 9)
        except (OSError, ValueError):
            pass


@pytest.mark.slow
def test_o42_a_run_that_ends_with_a_process_it_started_alive_fails_with_leak(proj, tmp_path):
    (proj / "tests" / "heavy" / "test_leak.py").write_text(LEAK, encoding="utf-8")
    pidfile = tmp_path / "leaked.pid"
    try:
        r = adapter(proj, "run", (tmp_path / "report").as_posix(), "--tier-arg", "tests/heavy/test_leak.py",
                    tier="heavy", extra={"LEAK_PIDFILE": pidfile.as_posix()})
        text = r.stdout + r.stderr
        assert r.returncode != 0, text
        assert re.search(r"^LEAK \d+ \S", text, re.M), text
    finally:
        _stop(pidfile)


@pytest.mark.slow
def test_o42_a_run_that_leaves_nothing_behind_does_not_report_leak(proj, tmp_path):
    r = adapter(proj, "run", (tmp_path / "report").as_posix(), "--ids", "tests/fast/test_basic.py::test_ok")
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert "LEAK" not in r.stdout + r.stderr
