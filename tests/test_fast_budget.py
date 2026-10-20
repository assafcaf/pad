"""E3-T7 R5, R6, R8: the suite guards itself (tests/conftest.py).

R5  a test not marked `slow` whose call phase exceeds `fast_test_budget` (pyproject.toml) fails
    with `FAST BUDGET <test id> <seconds>s: mark it slow or make it fast`.
R6  a process left behind by the session (its command line names this checkout's `payload/` or the
    session's temp root) is killed with its tree when the session ends, and the run fails with one
    `LEAK <pid> <command>` line per process, naming the test that started it.
R8  the `bg` fixture starts a payload script under the real bash and kills its whole tree at test
    end, whatever the outcome.

Each runs an inner pytest session (pytester) whose conftest is this repo's tests/conftest.py.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from conftest import BASH
from test_pad_proc import alive, wait_for

pytest_plugins = ["pytester"]

CONFTEST = (Path(__file__).resolve().parent / "conftest.py").as_posix()
PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def with_repo_conftest(pytester, budget: str = "100") -> None:
    """Make the inner session use this repo's conftest (hooks and fixtures) and a budget."""
    pytester.makeini(
        f"[pytest]\nfast_test_budget = {budget}\nmarkers =\n    slow: slow tests\n")
    pytester.makeconftest(
        "import importlib.util\n"
        f"_s = importlib.util.spec_from_file_location('pad_outer_conftest', r'{CONFTEST}')\n"
        "_m = importlib.util.module_from_spec(_s)\n"
        "_s.loader.exec_module(_m)\n"
        "globals().update({k: v for k, v in vars(_m).items() if not k.startswith('__')})\n")


def test_r5_the_repo_sets_a_positive_fast_test_budget_in_pyproject():
    m = re.search(r'^fast_test_budget\s*=\s*"?([0-9.]+)"?', PYPROJECT.read_text(encoding="utf-8"), re.M)
    assert m, "pyproject.toml has no fast_test_budget under [tool.pytest.ini_options]"
    assert float(m.group(1)) > 0


def test_r5_a_test_over_the_budget_fails_naming_itself_and_the_remedy(pytester):
    with_repo_conftest(pytester, budget="0.1")
    pytester.makepyfile(test_inner="import time\n\ndef test_slowpoke():\n    time.sleep(0.4)\n")
    result = pytester.runpytest()
    assert result.ret != 0
    result.assert_outcomes(failed=1)
    result.stdout.re_match_lines(
        [r".*FAST BUDGET \S*test_slowpoke\S* [0-9.]+s: mark it slow or make it fast"])


def test_r5_a_test_within_the_budget_passes(pytester):
    with_repo_conftest(pytester, budget="30")
    pytester.makepyfile(test_inner="def test_quick():\n    pass\n")
    pytester.runpytest().assert_outcomes(passed=1)


def test_r5_a_test_marked_slow_is_never_budgeted(pytester):
    with_repo_conftest(pytester, budget="0.1")
    pytester.makepyfile(test_inner=(
        "import time, pytest\n\n@pytest.mark.slow\ndef test_long():\n    time.sleep(0.4)\n\n"
        "def test_slowpoke():\n    time.sleep(0.4)\n"))
    result = pytester.runpytest()
    result.assert_outcomes(passed=1, failed=1)
    assert "test_long" not in "".join(
        ln for ln in result.stdout.lines if "FAST BUDGET" in ln)


LEAKER = '''
import subprocess, sys

def test_leaker(tmp_path):
    marker = str(tmp_path)
    subprocess.Popen(
        [r"{bash}", "-c", 'echo $$ > "$1"; sleep 300 & echo $! > "$2"; wait', marker,
         r"{pids}/leader.pid", r"{pids}/child.pid"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import time
    end = time.monotonic() + 60
    import os
    while time.monotonic() < end and not (os.path.exists(r"{pids}/child.pid")
                                          and open(r"{pids}/child.pid").read().strip()):
        time.sleep(0.05)
'''


@pytest.mark.slow
def test_r6_a_process_left_behind_is_killed_with_its_tree_and_fails_the_run_with_a_leak_line(pytester):
    with_repo_conftest(pytester)
    pids = pytester.path / "pids"
    pids.mkdir()
    pytester.makepyfile(test_inner=LEAKER.format(bash=BASH, pids=pids.as_posix()))
    result = pytester.runpytest_subprocess()
    child = None
    try:
        out = "\n".join(result.stdout.lines)
        assert result.ret != 0, out
        leaks = [ln for ln in result.stdout.lines if ln.startswith("LEAK ")]
        assert leaks, out
        assert all(re.match(r"LEAK \d+ \S", ln) for ln in leaks), leaks
        assert any("test_leaker" in ln for ln in leaks), leaks
        kids = list(pytester.path.glob("**/*.child")) + list(pids.glob("child.pid"))
        pid_files = [f for f in kids if f.read_text().strip()]
        assert pid_files, "the leaker never recorded its child"
        child = pid_files[0].read_text().strip()
        assert wait_for(lambda: not alive(child)), "the leaked process tree was not killed"
    finally:
        if child:
            subprocess.run([BASH, "-c", f"kill -9 {int(child)} 2>/dev/null; true"])


@pytest.mark.slow
def test_r6_a_session_that_leaves_nothing_behind_passes(pytester):
    with_repo_conftest(pytester)
    pytester.makepyfile(test_inner="def test_clean(tmp_path):\n    (tmp_path / 'x').write_text('x')\n")
    result = pytester.runpytest_subprocess()
    assert result.ret == 0, "\n".join(result.stdout.lines)
    assert not [ln for ln in result.stdout.lines if ln.startswith("LEAK ")]


BG_INNER = '''
import os, time

def test_starts_a_script_and_ends(repo, bg, tmp_path):
    child = r"{pids}/child.pid"
    p = bg.start("suite-slot.sh", "--", "bash", "-c", "echo $$ > '" + child + "'; exec sleep 300",
                 cwd=repo, env={{"PAD_SUITE_SLOTS": "1"}})
    end = time.monotonic() + 60
    while time.monotonic() < end and not (os.path.exists(child) and open(child).read().strip()):
        time.sleep(0.05)
    assert open(child).read().strip(), "the script never started"
    {ending}
'''


@pytest.mark.slow
@pytest.mark.parametrize("ending,failed", [("pass", 0), ("assert False, 'test failed'", 1)])
def test_r8_a_background_payload_script_is_gone_with_its_whole_tree_when_the_test_ends(
        pytester, ending, failed):
    with_repo_conftest(pytester)
    pids = pytester.path / "pids"
    pids.mkdir()
    pytester.makepyfile(test_inner=BG_INNER.format(pids=pids.as_posix(), ending=ending))
    result = pytester.runpytest_subprocess()
    child = None
    try:
        out = "\n".join(result.stdout.lines)
        result.assert_outcomes(passed=1 - failed, failed=failed)
        assert "LEAK" not in out, out
        child = (pids / "child.pid").read_text().strip()
        assert wait_for(lambda: not alive(child)), "the script's process tree survived the test"
    finally:
        if child:
            subprocess.run([BASH, "-c", f"kill -9 {int(child)} 2>/dev/null; true"])
