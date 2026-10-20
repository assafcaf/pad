"""E3-T3: merge-gate.sh with `## Test regime` tiers (O19, O20, O21, O22, O24, O52).

    merge-gate.sh --candidate <path> --gate fast --tickets K1[,K2...] --run <id> [--at <commit>]
    merge-gate.sh --gate heavy --head <sha> --run <id>        (run from the epic worktree)

With tiers, the `fast` gate runs the fast tier and then every listed ticket's acceptance tests
through `pad-test.sh --role gate`, reading failures from the adapter's `results` (no runner
output pattern of its own), then the config's typecheck and lint. `Tiers: none` in the regime
keeps today's gates: `fast` means `full`, and the adapter is never called. A gate that ends with
a process it started still alive fails with `LEAK <pid> <command>` lines, kills them, and prints
`REJECTED <KEY>: leak <n>`. The adapter is a double that logs each call with the HEAD it ran at
and decides pass or failure from files in the tree and env vars (see ADAPTER).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import BASH, BIN, git
from test_merge_gate import _config, _last

pytestmark = pytest.mark.slow

RUN = "E9"
T1, T2 = "E9-T1", "E9-T2"
HEAVY_ID = "tests/heavy/test_h.py::test_h"

ADAPTER = r"""#!/usr/bin/env bash
# Adapter double. Logs `<verb> <args> | HEAD=<sha of the cwd>` to $FAKE_LOG. `run` passes, or
# fails when a file BAD is in the tree, or $FAKE_FAIL_ARG is in its arguments. results.<n> in
# $FAKE_STATE overrides the n-th run. FAKE_HOLD holds a heavy run until $FAKE_STATE/release,
# FAKE_SLEEP delays a run, FAKE_LEAK leaves a child of the run alive after it ends.
verb="${1:-}"; [ $# -gt 0 ] && shift
echo "$verb $* | HEAD=$(git rev-parse HEAD 2>/dev/null)" >> "${FAKE_LOG:?}"
case "$verb" in
  run)
    rd="$1"; shift
    args="$*"
    n=$(( $(cat "${FAKE_STATE:?}/count" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$FAKE_STATE/count"
    mkdir -p "$rd"
    ids=""
    if [ "${1:-}" = --ids ]; then
      shift
      while [ $# -gt 0 ]; do case "$1" in --*) break ;; esac; ids="$ids $1"; shift; done
    else
      ids="tests/fast/test_a.py::test_x"
    fi
    case "$args" in *tests/heavy*)
      if [ -n "${FAKE_HOLD:-}" ]; then
        : > "$FAKE_STATE/held"
        for i in $(seq 1 600); do [ -f "$FAKE_STATE/release" ] && break; sleep 0.2; done
      fi ;;
    esac
    [ -z "${FAKE_SLEEP:-}" ] || sleep "$FAKE_SLEEP"
    if [ -n "${FAKE_LEAK:-}" ]; then
      nohup sleep 300 </dev/null >/dev/null 2>&1 &
      echo $! > "$FAKE_STATE/leakpid"
      sleep 3
    fi
    bad=0
    [ -f BAD ] && bad=1
    if [ -n "${FAKE_FAIL_ARG:-}" ]; then case "$args" in *"$FAKE_FAIL_ARG"*) bad=1 ;; esac; fi
    if [ -f "$FAKE_STATE/results.$n" ]; then
      cp "$FAKE_STATE/results.$n" "$rd/results"
    else
      for id in $ids; do
        if [ "$bad" = 1 ]; then echo "failure ${FAKE_FAIL_ID:-$id} boom"; else echo "pass $id"; fi
      done > "$rd/results"
    fi
    grep -qE '^(failure|error) ' "$rd/results" && exit 1
    exit 0 ;;
  results) cat "${1:?}/results" ;;
  runner-names) echo fake ;;
  protected-files) echo 'conftest.fake' ;;
  acceptance-pattern) echo "tests/**/*${1:-}*" ;;
  capabilities) echo "${FAKE_CAPS-contract-fast leak-check shuffle}" ;;
  *) echo "fake adapter: unknown verb '$verb'" >&2; exit 64 ;;
esac
"""

REGIME = """
## Test regime

Runner: fake
{tiers}Repeat limit: 3
Ticket run limit: 12

| Tier | Adapter selector | Per-test kill | Budget | Declared GB | Workers |
|---|---|---|---|---|---|
| fast | tests/fast | 60 | {budget} | 0.5 | 2 |
| heavy | tests/heavy | 300 | 600 | 2 | 1 |
| epic | tests/epic | 900 | 1800 | 4 | 1 |
"""


def write_bytes(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def commit_files(wt: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        write_bytes(wt / rel, text)
        git("add", rel, cwd=wt)
    git("commit", "-q", "-m", msg, cwd=wt)
    return git("rev-parse", "HEAD", cwd=wt)


def alive(pid: str) -> bool:
    return subprocess.run([BASH, "-c", f"kill -0 {pid}"], capture_output=True).returncode == 0


def kill(pid: str) -> None:
    subprocess.run([BASH, "-c", f"kill -9 {pid}"], capture_output=True)


def wait_for(cond, timeout=120.0, step=0.2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(step)
    return cond()


def base_env(state: Path, fake_log: Path, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("PAD_MEMORY", "PAD_HOST", "PAD_SUITE", "PAD_CAP", "PAD_CORES", "PAD_CONTAIN"))}
    env.update(PAD_MEMORY_PROBE="echo 1", PAD_MEMORY_TOTAL_GB="16", PAD_CONTAIN="group",
               PAD_SAMPLE_INTERVAL="1", PAD_CORES="64", PAD_SUITE_SLOTS="4",
               FAKE_STATE=state.as_posix(), FAKE_LOG=fake_log.as_posix())
    env.update(extra)
    return env


class TEnv:
    """An epic worktree whose config has Commands rows that log, a `## Test regime`, and the
    adapter double installed as the repo's own; a detached candidate on the epic head."""

    def __init__(self, repo, worktree, tmp_path, *, tiers_none=False, budget=600, **cmds):
        self.repo = repo
        self.log = tmp_path / "ran.log"
        self.state = tmp_path / "fake-state"
        self.state.mkdir()
        self.fake_log = tmp_path / "fake.log"
        self.fake_log.write_text("", encoding="utf-8")
        self.epic = worktree(repo, "epic")
        cfg = _config(self.log, **cmds) + REGIME.format(
            tiers="Tiers: none\n" if tiers_none else "", budget=budget)
        self.epic_head = commit_files(self.epic, {
            ".claude/workflow/config.md": cfg,
            ".claude/pad-plugins/runners/fake.sh": ADAPTER,
            ".gitignore": ".work/\n",
            "src/base.py": "BASE = 1\n",
            "tests/test_other.py": "def test_o():\n    pass\n",
            "tests/fast/test_a.py": "def test_x():\n    pass\n",
            "tests/heavy/test_h.py": "def test_h():\n    pass\n",
        }, "epic: base")
        git("push", "-q", "-u", "origin", "epic", cwd=self.epic)
        self.cand = repo.parent / "cand"
        git("worktree", "add", "-q", "--detach", self.cand.as_posix(), self.epic_head, cwd=repo)

    def commit(self, files: dict[str, str], msg: str = "batch") -> str:
        return commit_files(self.cand, files, msg)

    def env(self, **extra: str) -> dict[str, str]:
        return base_env(self.state, self.fake_log, **extra)

    def gate(self, *args: str, **env):
        return subprocess.run(
            [BASH, (BIN / "merge-gate.sh").as_posix(), "--candidate", self.cand.as_posix(),
             "--run", RUN, *args],
            cwd=str(self.epic), env=self.env(**env), capture_output=True, text=True,
            encoding="utf-8", timeout=170)

    def ran(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").split() if self.log.exists() else []

    def adapter_calls(self, verb: str = "run") -> list[str]:
        return [x for x in self.fake_log.read_text(encoding="utf-8").splitlines()
                if x.startswith(verb + " ")]

    def gates(self) -> list[dict]:
        f = self.repo / ".work" / "runs" / RUN / "gates.jsonl"
        if not f.is_file():
            return []
        return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]

    def run_log(self) -> str:
        f = self.repo / ".work" / "runs" / RUN / "progress.md"
        return f.read_text(encoding="utf-8") if f.is_file() else ""


@pytest.fixture
def tenv(repo, worktree, tmp_path):
    def make(**kw) -> TEnv:
        return TEnv(repo, worktree, tmp_path, **kw)
    return make


def out(r) -> str:
    return r.stdout + r.stderr


# --- O20: the fast gate = fast tier + each ticket's acceptance tests, through pad-test --------

def test_o20_fast_gate_runs_the_fast_tier_and_each_tickets_acceptance_tests_as_role_gate(tenv):
    e = tenv()
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate("--gate", "fast", "--tickets", f"{T1},{T2}")
    assert _last(r) == "GATE PASS", out(r)
    assert r.returncode == 0
    gates = e.gates()
    assert {g["role"] for g in gates} == {"gate"}, gates
    assert {g["selection"] for g in gates} == {"fast", f"acceptance:{T1}", f"acceptance:{T2}"}, gates
    runs = e.adapter_calls("run")
    assert len(runs) == 3, runs
    assert sum("tests/fast" in x for x in runs) == 1, runs
    assert sum(T1 in x for x in runs) == 1 and sum(T2 in x for x in runs) == 1, runs
    assert "LEAK" not in out(r)


def test_o20_fast_gate_does_not_run_the_full_suite_command_but_still_typechecks_and_lints(tenv):
    e = tenv()
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate("--gate", "fast", "--tickets", T1)
    assert _last(r) == "GATE PASS", out(r)
    assert e.ran() == ["typecheck", "lint"]


def test_o20_a_red_fast_tier_fails_the_gate_and_stops_before_typecheck_and_lint(tenv):
    e = tenv()
    e.commit({"tests/test_new.py": "def test_new():\n    pass\n"})
    r = e.gate("--gate", "fast", "--tickets", T1,
               FAKE_FAIL_ARG="tests/fast", FAKE_FAIL_ID="tests/test_new.py::test_new")
    assert _last(r) == "GATE FAIL", out(r)
    assert r.returncode == 1
    assert e.ran() == []


def test_o20_a_red_acceptance_test_fails_the_gate_though_the_fast_tier_is_green(tenv):
    e = tenv()
    e.commit({"tests/test_new.py": "def test_new():\n    pass\n"})
    r = e.gate("--gate", "fast", "--tickets", f"{T1},{T2}",
               FAKE_FAIL_ARG=T2, FAKE_FAIL_ID="tests/test_new.py::test_new")
    assert _last(r) == "GATE FAIL", out(r)
    assert r.returncode == 1
    assert e.ran() == []
    assert any(g["selection"] == "fast" and g["outcome"] == "pass" for g in e.gates()), e.gates()


# --- O19: failures are read through the adapter, not from a runner's output pattern ----------

def test_o19_a_failure_outside_the_batch_read_from_the_adapter_is_rerun_once_and_a_green_rerun_counts(tenv):
    e = tenv()
    e.commit({"src/impl.py": "X = 1\n"})
    # the first fast run fails in a file the batch neither changed nor imports; the adapter says
    # so only in its `results` lines (no `FAILED <id>` text anywhere in the output)
    (e.state / "results.1").write_bytes(b"failure tests/test_other.py::test_o boom\n")
    r = e.gate("--gate", "fast", "--tickets", T1)
    assert _last(r) == "GATE PASS", out(r)
    fast = [x for x in e.adapter_calls("run") if "tests/fast" in x]
    assert len(fast) == 2, fast


def test_o19_a_failure_inside_the_batch_read_from_the_adapter_is_not_rerun(tenv):
    e = tenv()
    e.commit({"tests/test_new.py": "def test_new():\n    pass\n"})
    r = e.gate("--gate", "fast", "--tickets", T1,
               FAKE_FAIL_ARG="tests/fast", FAKE_FAIL_ID="tests/test_new.py::test_new")
    assert _last(r) == "GATE FAIL", out(r)
    fast = [x for x in e.adapter_calls("run") if "tests/fast" in x]
    assert len(fast) == 1, fast


# --- O21: over budget is a signal, not a rejection -------------------------------------------

def test_o21_a_green_gate_over_its_tier_budget_lands_and_logs_over_budget(tenv):
    e = tenv(budget=1)
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate("--gate", "fast", "--tickets", T1, FAKE_SLEEP="3")
    assert _last(r) == "GATE PASS", out(r)
    assert r.returncode == 0
    m = re.search(r"^GATE OVER-BUDGET fast (\d+)s?/1s?\s*$", e.run_log(), re.M)
    assert m, e.run_log()
    assert int(m.group(1)) >= 2


def test_o21_a_gate_within_budget_logs_no_over_budget_line(tenv):
    e = tenv(budget=600)
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate("--gate", "fast", "--tickets", T1)
    assert _last(r) == "GATE PASS", out(r)
    assert "OVER-BUDGET" not in e.run_log() + out(r)


# --- O22: heavy runs at the given head without blocking the next fast batch -------------------

def test_o22_heavy_runs_at_the_given_head_while_a_fast_batch_gates_and_lands(tenv):
    e = tenv()
    c1 = e.commit({"src/one.py": "ONE = 1\n"}, "batch one")
    c2 = e.commit({"src/two.py": "TWO = 1\n"}, "batch two")
    env = e.env(FAKE_HOLD="1")
    heavy = subprocess.Popen(
        [BASH, (BIN / "merge-gate.sh").as_posix(), "--gate", "heavy", "--head", c1, "--run", RUN],
        cwd=str(e.epic), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8")
    try:
        assert wait_for(lambda: (e.state / "held").exists() or heavy.poll() is not None), "heavy never started"
        assert heavy.poll() is None, heavy.stdout.read()
        fast = e.gate("--gate", "fast", "--tickets", T1, "--at", c2, FAKE_HOLD="1")
        assert _last(fast) == "GATE PASS", out(fast)
        assert heavy.poll() is None  # the fast gate did not wait for heavy, nor end it
        (e.state / "release").write_text("go\n", encoding="utf-8")
        text, _ = heavy.communicate(timeout=150)
    finally:
        if heavy.poll() is None:
            heavy.kill()
    assert text.strip().splitlines()[-1] == "GATE PASS", text
    assert heavy.returncode == 0
    heavy_runs = [x for x in e.adapter_calls("run") if "tests/heavy" in x]
    assert len(heavy_runs) == 1 and heavy_runs[0].endswith(f"HEAD={c1}"), heavy_runs
    assert any(g["selection"] == "heavy" and g["role"] == "gate" for g in e.gates()), e.gates()


# --- O24: Tiers: none keeps today's gates ----------------------------------------------------

def test_o24_with_tiers_none_a_fast_gate_is_the_full_suite_and_the_adapter_is_never_called(tenv):
    e = tenv(tiers_none=True)
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate("--gate", "fast", "--tickets", T1)
    assert _last(r) == "GATE PASS", out(r)
    assert e.ran() == ["gate", "typecheck", "lint"]
    assert e.adapter_calls("run") == []
    assert e.gates() == []


def test_o24_with_tiers_none_a_red_full_suite_still_fails_the_gate(tenv):
    e = tenv(tiers_none=True, full="echo boom-marker; exit 1")
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate("--gate", "fast", "--tickets", T1)
    assert _last(r) == "GATE FAIL", out(r)
    assert "boom-marker" in r.stdout
    assert e.ran() == ["gate"]


# --- O52: a gate that ends with a process it started alive fails with LEAK -------------------

LEAKER = "sleep 300 </dev/null >/dev/null 2>&1 & echo $! > \"{pidfile}\"; sleep 3"


def _assert_leak_rejected(e, r, pidfile: Path):
    pid = pidfile.read_text(encoding="utf-8").strip() if pidfile.exists() else ""
    try:
        assert _last(r) == "GATE FAIL", out(r)
        assert r.returncode == 1
        leaks = re.findall(r"^LEAK (\d+) (.+)$", r.stdout, re.M)
        assert len(leaks) == 1, out(r)
        assert "sleep" in leaks[0][1], leaks
        assert f"REJECTED {T1}: leak 1" in r.stdout, out(r)
        assert re.search(r"^LEAK \d+ .*sleep", e.run_log(), re.M), e.run_log()
        assert pid, "the leaking process never started"
        assert wait_for(lambda: not alive(pid), timeout=30), f"leaked process {pid} was not killed"
    finally:
        if pid:
            kill(pid)


def test_o52_a_full_gate_that_leaves_a_process_alive_fails_with_leak_and_kills_it(tenv, tmp_path):
    pidfile = tmp_path / "leak.pid"
    e = tenv(tiers_none=True, full=LEAKER.format(pidfile=pidfile.as_posix()))
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate("--gate", "full", "--tickets", T1)
    _assert_leak_rejected(e, r, pidfile)


def test_o52_a_fast_gate_leak_fails_even_when_the_adapter_declares_no_leak_check(tenv):
    e = tenv()
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate("--gate", "fast", "--tickets", T1, FAKE_LEAK="1", FAKE_CAPS="")
    _assert_leak_rejected(e, r, e.state / "leakpid")


# --- K1: a leaked process is reported with the command it has at the end, and gone before FAIL --

# The child starts as a bash (its command line when first listed) and execs `sleep 600` a moment
# later; it also leaves a grandchild, `sleep 601`, that only a tree kill reaches.
SHAPESHIFTER = (
    "bash -c 'echo $$ > \"{pidfile}\"; sleep 601 </dev/null >/dev/null 2>&1 & "
    "echo $! > \"{pidfile}.kid\"; sleep 1; exec sleep 600' </dev/null >/dev/null 2>&1 & sleep 3"
)


def _shapeshifter_gate(tenv, tmp_path):
    pidfile = tmp_path / "shape.pid"
    e = tenv(tiers_none=True, full=SHAPESHIFTER.format(pidfile=pidfile.as_posix()))
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate("--gate", "full", "--tickets", T1)
    return pidfile, r


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def _check_shapeshifter(pidfile, r):
    pid, kid = _read(pidfile), _read(Path(str(pidfile) + ".kid"))
    try:
        assert pid and kid, "the leaking process never started"
        assert _last(r) == "GATE FAIL", out(r)
        leaks = re.findall(r"^LEAK (\d+) (.+)$", r.stdout, re.M)
        mine = [c for p, c in leaks if p == pid]
        assert mine, f"no LEAK line for pid {pid}: {out(r)}"
        assert mine[0].strip() == "sleep 600", mine
        # gone at the moment the gate reports, not eventually
        assert not alive(pid), f"leaked process {pid} still alive at GATE FAIL"
        assert not alive(kid), f"leaked process {pid}'s child {kid} still alive at GATE FAIL"
    finally:
        for p in (pid, kid):
            if p:
                kill(p)


def test_k1_a_leaked_process_that_execs_is_reported_with_its_final_command_and_gone_at_gate_fail(
        tenv, tmp_path):
    pidfile, r = _shapeshifter_gate(tenv, tmp_path)
    _check_shapeshifter(pidfile, r)


@pytest.mark.slow
def test_k1_the_same_holds_with_eight_busy_workers_running_at_once(tenv, tmp_path):
    busy = [subprocess.Popen([sys.executable, "-c", "while True: pass"]) for _ in range(8)]
    try:
        pidfile, r = _shapeshifter_gate(tenv, tmp_path)
        _check_shapeshifter(pidfile, r)
    finally:
        for b in busy:
            b.kill()
        for b in busy:
            b.wait(timeout=30)
