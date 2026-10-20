"""E3-T2 O41, O42, O9: the vitest runner adapter, runners/vitest.sh.

Same verbs as pytest.sh (see test_runner_pytest.py); ids are `<file> > <suite> > <test>` with the
file relative to the project. `run` starts vitest as `${PAD_VITEST:-npx vitest} run
--reporter=json --outputFile=<report-dir>/vitest.json <selector or ids>` and `results` reads
that JSON (the shape vitest's json reporter writes: testResults[].assertionResults[]). The tests
that need a real vitest are reported as "did not run" (a skip) where vitest is not installed.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import pytest

from conftest import BASH, BIN, ROOT

ADAPTER = (BIN.parent / "runners" / "vitest.sh").as_posix()
FAKE = (ROOT / "tests" / "fixtures" / "runners" / "fake_vitest.sh").as_posix()

REPORT = {
    "numTotalTests": 4,
    "testResults": [
        {"name": "src/dial.test.ts", "status": "failed", "message": "", "assertionResults": [
            {"ancestorTitles": ["dial"], "fullName": "dial turns", "title": "turns", "status": "passed",
             "failureMessages": []},
            {"ancestorTitles": ["dial"], "fullName": "dial sticks", "title": "sticks", "status": "failed",
             "failureMessages": ["AssertionError: expected 1 to be 2"]},
            {"ancestorTitles": ["dial", "inner"], "fullName": "dial inner later", "title": "later",
             "status": "pending", "failureMessages": []},
        ]},
        {"name": "src/broken.test.ts", "status": "failed", "message": "Failed to load url ./nope",
         "assertionResults": []},
    ],
}


def need_vitest(proj: Path) -> None:
    node = shutil.which("node")
    ok = node and subprocess.run([node, "-e", "require.resolve('vitest')"], cwd=str(proj),
                                 capture_output=True).returncode == 0
    if not ok:
        raise unittest.SkipTest("did not run: vitest is not installed here")


@pytest.fixture
def proj(tmp_path):
    d = tmp_path / "proj"
    (d / "src").mkdir(parents=True)
    return d


def adapter(proj: Path, *args: str, tier: str = "", extra: dict | None = None, timeout: float = 170):
    env = {k: v for k, v in os.environ.items() if k != "PAD_TIER"}
    if tier:
        env["PAD_TIER"] = tier
    env.update(extra or {})
    return subprocess.run([BASH, ADAPTER, *args], cwd=str(proj), env=env, capture_output=True,
                          text=True, encoding="utf-8", timeout=timeout)


def fake_env(tmp_path: Path, exit_code: int = 1) -> dict[str, str]:
    j = tmp_path / "report.json"
    j.write_text(json.dumps(REPORT), encoding="utf-8")
    return {"PAD_VITEST": f"bash {FAKE}", "FAKE_VITEST_JSON": j.as_posix(),
            "FAKE_VITEST_EXIT": str(exit_code), "FAKE_LOG": (tmp_path / "vitest.log").as_posix()}


def test_the_adapter_names_its_runner_surface_and_capabilities(proj):
    names = adapter(proj, "runner-names")
    assert names.returncode == 0 and "vitest" in names.stdout
    prot = adapter(proj, "protected-files")
    assert prot.returncode == 0 and "vitest" in prot.stdout
    acc = adapter(proj, "acceptance-pattern", "E3-T2")
    assert acc.returncode == 0 and "E3-T2" in acc.stdout and ".test." in acc.stdout
    caps = adapter(proj, "capabilities").stdout.split()
    assert {"contract-fast", "leak-check"} <= set(caps), caps


@pytest.mark.slow
def test_results_maps_vitest_json_to_ids_and_kinds(proj, tmp_path):
    env = fake_env(tmp_path)
    report = tmp_path / "report"
    r = adapter(proj, "run", report.as_posix(), "--tier-arg", "src", extra=env)
    assert r.returncode == 1, (r.stdout, r.stderr)
    res = adapter(proj, "results", report.as_posix(), extra=env)
    assert res.returncode == 0, res.stderr
    lines = res.stdout.splitlines()
    assert "pass src/dial.test.ts > dial > turns" in lines
    assert any(re.fullmatch(r"failure src/dial\.test\.ts > dial > sticks .*expected 1 to be 2", x) for x in lines), lines
    assert "skipped src/dial.test.ts > dial > inner > later" in lines
    assert any(x.startswith("error src/broken.test.ts") and "Failed to load" in x for x in lines), lines
    assert len(lines) == 4, lines


@pytest.mark.slow
def test_run_hands_the_selection_to_vitest_in_json_form(proj, tmp_path):
    env = fake_env(tmp_path)
    report = tmp_path / "report"
    adapter(proj, "run", report.as_posix(), "--ids", "src/dial.test.ts > dial > turns", extra=env)
    log = (tmp_path / "vitest.log").read_text(encoding="utf-8")
    assert "run" in log and "--reporter=json" in log, log
    assert f"--outputFile={report.as_posix()}" in log.replace("\\", "/"), log


@pytest.mark.slow
def test_results_of_a_run_that_never_wrote_a_report_are_empty(proj, tmp_path):
    report = tmp_path / "report"
    env = fake_env(tmp_path)
    env["PAD_VITEST"] = "bash -c 'exit 1'"
    adapter(proj, "run", report.as_posix(), "--tier-arg", "src", extra=env)
    res = adapter(proj, "results", report.as_posix(), extra=env)
    assert res.returncode == 0 and res.stdout.strip() == "", (res.stdout, res.stderr)


# --- O41, O42 against a real vitest ----------------------------------------------------------

NET_TEST = '''\
import { test } from "vitest";
import net from "node:net";
test("opens a socket", () => { const s = new net.Socket(); s.connect(1, "127.0.0.1"); });
'''

OK_TEST = 'import { test, expect } from "vitest";\ntest("fine", () => { expect(1).toBe(1); });\n'


@pytest.mark.slow
def test_o41_in_the_fast_tier_a_test_that_opens_a_socket_fails_at_the_call(proj, tmp_path):
    need_vitest(proj)
    (proj / "src" / "net.test.ts").write_text(NET_TEST, encoding="utf-8")
    (proj / "src" / "ok.test.ts").write_text(OK_TEST, encoding="utf-8")
    report = tmp_path / "report"
    r = adapter(proj, "run", report.as_posix(), "--tier-arg", "src", tier="fast")
    assert r.returncode == 1, (r.stdout, r.stderr)
    res = adapter(proj, "results", report.as_posix()).stdout
    assert re.search(r"^failure src/net\.test\.ts > opens a socket", res, re.M), res
    assert re.search(r"^pass src/ok\.test\.ts > fine", res, re.M), res


LEAK_TEST = '''\
import { test } from "vitest";
import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";
test("leaves a child running", () => {
  const c = spawn(process.execPath, ["-e", "setTimeout(() => {}, 300000)"], { detached: true, stdio: "ignore" });
  c.unref();
  writeFileSync(process.env.LEAK_PIDFILE as string, String(c.pid));
});
'''


@pytest.mark.slow
def test_o42_a_run_that_ends_with_a_process_it_started_alive_fails_with_leak(proj, tmp_path):
    need_vitest(proj)
    (proj / "src" / "leak.test.ts").write_text(LEAK_TEST, encoding="utf-8")
    pidfile = tmp_path / "leaked.pid"
    try:
        r = adapter(proj, "run", (tmp_path / "report").as_posix(), "--tier-arg", "src",
                    tier="heavy", extra={"LEAK_PIDFILE": pidfile.as_posix()})
        text = r.stdout + r.stderr
        assert r.returncode != 0, text
        assert re.search(r"^LEAK \d+ \S", text, re.M), text
    finally:
        if pidfile.is_file():
            try:
                os.kill(int(pidfile.read_text().strip()), 9)
            except (OSError, ValueError):
                pass
