"""The pytest runner plugin of PAD's pytest adapter (runners/pytest.sh loads it with `-p`).

It writes what the adapter's `results` verb reads, and enforces the two contracts a runner can
declare:

* results: one line per test in `$PAD_REPORT_DIR/results`, `pass|failure|error|skipped <id> [<msg>]`.
  A test that fails an assertion is a `failure`; a setup, teardown or collection problem (an
  import that cannot load) is an `error`.
* contract-fast: with `PAD_TIER=fast`, a test that opens a socket or starts a subprocess fails at
  the call.
* leak-check: processes the tests started (through subprocess) that are still alive when the
  session ends are recorded in `$PAD_REPORT_DIR/leaks` as `<pid> <command>` and killed; the
  adapter turns them into `LEAK <pid> <command>`.
* shuffle: with `PAD_SHUFFLE=1` the collected tests run in a random order.
"""
from __future__ import annotations

import os
import random
import socket
import subprocess

import pytest

_REPORT = os.environ.get("PAD_REPORT_DIR", "")
_FAST = os.environ.get("PAD_TIER", "") == "fast"
_active = False
_started: list = []


def _append(name: str, line: str) -> None:
    if not _REPORT:
        return
    os.makedirs(_REPORT, exist_ok=True)
    with open(os.path.join(_REPORT, name), "a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")


def _one_line(text: str) -> str:
    text = " ".join(str(text).split())
    return text[:300]


class _Contract(AssertionError):
    pass


def _install() -> None:
    orig_init = subprocess.Popen.__init__
    orig_sock = socket.socket.__init__

    def popen_init(self, *args, **kwargs):
        if _active and _FAST:
            raise _Contract("PAD fast-tier contract: a fast test must not start a subprocess")
        orig_init(self, *args, **kwargs)
        if _active:
            _started.append(self)

    def sock_init(self, *args, **kwargs):
        if _active and _FAST:
            raise _Contract("PAD fast-tier contract: a fast test must not open a socket")
        orig_sock(self, *args, **kwargs)

    subprocess.Popen.__init__ = popen_init
    socket.socket.__init__ = sock_init


_install()


_is_worker = False


def pytest_configure(config):
    global _is_worker
    _is_worker = hasattr(config, "workerinput")


def pytest_collection_modifyitems(items):
    if os.environ.get("PAD_SHUFFLE") == "1":
        random.shuffle(items)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    global _active
    _active = True
    try:
        yield
    finally:
        _active = False


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    global _active
    _active = True
    try:
        yield
    finally:
        _active = False


def _message(report) -> str:
    lr = report.longrepr
    if lr is None:
        return ""
    crash = getattr(lr, "reprcrash", None)
    if crash is not None and getattr(crash, "message", None):
        return _one_line(crash.message)
    if isinstance(lr, tuple) and len(lr) == 3:
        return _one_line(lr[2])
    text = getattr(report, "longreprtext", "") or str(lr)
    lines = [x for x in text.splitlines() if x.strip()]
    return _one_line(lines[-1]) if lines else ""


def pytest_runtest_logreport(report):
    # Under xdist the workers run the plugin too; only the controller writes the results.
    if _is_worker:
        return
    ident = report.nodeid
    if report.when == "call":
        if report.passed:
            _append("results", f"pass {ident}")
        elif report.failed:
            _append("results", f"failure {ident} {_message(report)}".rstrip())
        else:
            _append("results", f"skipped {ident} {_message(report)}".rstrip())
    elif report.when == "setup":
        if report.failed:
            _append("results", f"error {ident} {_message(report)}".rstrip())
        elif report.skipped:
            _append("results", f"skipped {ident} {_message(report)}".rstrip())
    elif report.when == "teardown" and report.failed:
        _append("results", f"error {ident} {_message(report)}".rstrip())


def pytest_collectreport(report):
    if report.failed:
        _append("results", f"error {report.nodeid} {_message(report)}".rstrip())


def pytest_sessionfinish(session, exitstatus):
    for p in _started:
        try:
            alive = p.poll() is None
        except Exception:
            alive = False
        if alive:
            cmd = p.args if isinstance(p.args, str) else " ".join(str(x) for x in p.args)
            _append("leaks", f"{p.pid} {_one_line(cmd)}")
            try:
                p.kill()
            except Exception:
                pass
