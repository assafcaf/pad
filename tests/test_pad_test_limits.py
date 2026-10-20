"""E3-T2 O16: pad-test-limits.sh, the ticket's repeat and run limits.

    pad-test-limits.sh show  --run <id> --ticket <KEY>
        prints `LIMITS <KEY> repeat=<n> runs=<n>`: the config's `Repeat limit:` / `Ticket run
        limit:` (defaults 3 and 12), or what `raise` set for this ticket in this run.
    pad-test-limits.sh raise --run <id> --ticket <KEY> [--repeat <n>] [--runs <n>]
        sets the ticket's limits for the run (only /pad-run, on the operator's word, calls it) and
        prints the same line. Exit 64 on usage.
pad-test.sh reads the limits through it.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures" / "runners"))
from harness import Harness, LIMITS, out  # noqa: E402

from conftest import BASH  # noqa: E402

LINE = re.compile(r"^LIMITS (\S+) repeat=(\d+) runs=(\d+)$", re.M)


def limits(h: Harness, *args: str):
    return subprocess.run([BASH, LIMITS, *args], cwd=str(h.repo), env=h.env(), capture_output=True,
                          text=True, encoding="utf-8", timeout=120)


def shown(r) -> tuple[str, int, int]:
    m = LINE.search(r.stdout)
    assert m, out(r)
    return m.group(1), int(m.group(2)), int(m.group(3))


@pytest.fixture
def h(repo, tmp_path):
    return Harness(repo, tmp_path)


def test_o16_the_limits_default_to_the_configs(h):
    r = limits(h, "show", "--run", "E9", "--ticket", "E9-T1")
    assert r.returncode == 0, out(r)
    assert shown(r) == ("E9-T1", 3, 12)


def test_o16_the_configs_values_are_read(repo, tmp_path):
    h = Harness(repo, tmp_path, repeat="5", runs="20")
    assert shown(limits(h, "show", "--run", "E9", "--ticket", "E9-T1")) == ("E9-T1", 5, 20)


def test_o16_raise_changes_only_that_ticket_and_that_limit(h):
    r = limits(h, "raise", "--run", "E9", "--ticket", "E9-T1", "--repeat", "6")
    assert r.returncode == 0, out(r)
    assert shown(r) == ("E9-T1", 6, 12)
    assert shown(limits(h, "show", "--run", "E9", "--ticket", "E9-T1")) == ("E9-T1", 6, 12)
    assert shown(limits(h, "show", "--run", "E9", "--ticket", "E9-T2")) == ("E9-T2", 3, 12)
    assert shown(limits(h, "show", "--run", "E10", "--ticket", "E9-T1")) == ("E9-T1", 3, 12)
    limits(h, "raise", "--run", "E9", "--ticket", "E9-T1", "--runs", "30")
    assert shown(limits(h, "show", "--run", "E9", "--ticket", "E9-T1")) == ("E9-T1", 6, 30)


@pytest.mark.slow
def test_o16_pad_test_honours_a_raised_repeat_limit(repo, tmp_path):
    h = Harness(repo, tmp_path, repeat="1", runs="12")
    assert h.run("--tier", "fast").returncode == 0
    h.change_tree()
    assert h.run("--tier", "fast").returncode == 65
    limits(h, "raise", "--run", "E9", "--ticket", "E9-T1", "--repeat", "2")
    h.change_tree()
    r = h.run("--tier", "fast")
    assert r.returncode == 0, out(r)


@pytest.mark.parametrize("args", [
    [],
    ["show"],
    ["show", "--run", "E9"],
    ["raise", "--run", "E9", "--ticket", "E9-T1"],
    ["raise", "--run", "E9", "--ticket", "E9-T1", "--repeat", "many"],
    ["frobnicate", "--run", "E9", "--ticket", "E9-T1"],
])
def test_o16_bad_usage_is_64(h, args):
    assert limits(h, *args).returncode == 64
