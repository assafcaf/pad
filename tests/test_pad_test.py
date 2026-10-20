"""E3-T2: pad-test.sh, the only way tests run (O2, O3, O9, O12-O17).

    pad-test.sh --run <id> --ticket <KEY> --role owner|test-designer|gate|suite-owner|operator
                (--tier <name> | --ids <id>... | --failed | --acceptance <KEY>) [--workers n]
    pad-test.sh --self-test
    exit: 0 pass, 1 tests failed, 2 did not run, 64 usage, 65 refused (REPEAT, RUN LIMIT, NARROW,
          TIER REFUSED), 75 CAP KILLED

It reads `## Test regime` of `.claude/workflow/config.md` (`Runner:`, `Repeat limit:`, `Ticket run
limit:`, the tiers table), finds `runners/<Runner>.sh` first in the repo's
`.claude/pad-plugins/runners/`, then next to the workflow `bin/`, and talks to it through the
verbs only. The tests install tests/fixtures/runners/fake.sh as the repo's own adapter, which
logs each call and plays back results. A selection's id is `--tier` name or its `--ids`; the tree
is the commit plus the working-tree hash (the .work/ directory is ignored). A run ends with one
line in <main>/.work/runs/<id>/gates.jsonl; the run's flake file is <main>/.work/runs/<id>/flakes.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures" / "runners"))
from harness import Harness, out  # noqa: E402

from conftest import BASH, BIN, ROOT  # noqa: E402

slow = pytest.mark.slow
A = "tests/fast/test_a.py"


@pytest.fixture
def h(repo, tmp_path):
    return Harness(repo, tmp_path)


# --- O2: the default cap ---------------------------------------------------------------------

@slow
def test_o2_with_no_host_md_the_run_says_once_that_it_uses_85_percent(h):
    r = h.run("--tier", "fast")
    assert r.returncode == 0, out(r)
    said = [x for x in r.stderr.splitlines() if "85%" in x]
    assert len(said) == 1, r.stderr


@slow
def test_o2_a_host_md_cap_is_used_and_the_default_is_not_announced(h):
    (h.repo / ".claude" / "workflow" / "host.md").write_text(
        "OS: test\nMemory total: 16 GB\nMemory cap: 50%\nSelf-test: ok\n", encoding="utf-8")
    r = h.run("--tier", "fast")
    assert r.returncode == 0, out(r)
    assert "85%" not in r.stderr, r.stderr


# --- O3: containment self-test ---------------------------------------------------------------

@slow
def test_o3_self_test_proves_containment_and_names_the_mechanism(h):
    r = subprocess.run([BASH, (BIN / "pad-test.sh").as_posix(), "--self-test"], cwd=str(h.repo),
                       env={**h.env(), "PAD_CONTAIN": ""}, capture_output=True, text=True, timeout=170)
    assert r.returncode == 0, out(r)
    assert re.search(r"^SELF-TEST containment ok (job-object|process-group)$", r.stdout, re.M), out(r)


# --- O9: the adapter is the only door to the runner ------------------------------------------

@slow
def test_o9_a_run_calls_only_adapter_verbs(h):
    h.results(1, f"pass {A}::test_x")
    r = h.run("--tier", "fast")
    assert r.returncode == 0, out(r)
    verbs = h.verbs()
    assert "run" in verbs and "results" in verbs, verbs
    assert set(verbs) <= {"run", "results", "capabilities", "runner-names", "protected-files",
                          "acceptance-pattern", "mutate"}, verbs


def test_o9_no_runner_name_outside_a_comment_in_the_bin_scripts():
    # affected-tests.sh (manifest globs) and vitest-gate.sh (the worked example) are out of this
    # ticket's reach; merge-gate.sh moves onto the adapter in T3.
    skip = {"merge-gate.sh", "vitest-gate.sh", "affected-tests.sh"}
    names = re.compile(r"pytest|vitest|jest", re.I)
    found = []
    for f in sorted(BIN.glob("*.sh")):
        if f.name in skip:
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if names.search(line):
                found.append(f"{f.name}:{i}: {line.strip()}")
    assert found == []


# --- O12: a whole file is not an id ----------------------------------------------------------

@slow
def test_o12_a_whole_file_as_an_id_exits_64_with_the_id_form(h):
    r = h.run("--ids", A)
    assert r.returncode == 64, out(r)
    assert "<file>::<test>" in r.stderr, r.stderr


@slow
def test_o12_a_full_test_id_is_passed_to_the_adapter(h):
    h.results(1, f"pass {A}::test_x")
    r = h.run("--ids", f"{A}::test_x")
    assert r.returncode == 0, out(r)
    assert any(f"{A}::test_x" in c for c in h.calls("run")), h.calls("run")


# --- O13: tiers an agent may not ask for -----------------------------------------------------

@slow
@pytest.mark.parametrize("role", ["owner", "test-designer"])
@pytest.mark.parametrize("tier", ["heavy", "epic"])
def test_o13_an_agent_role_asking_for_heavy_or_epic_is_refused_65(h, role, tier):
    r = h.run("--tier", tier, role=role)
    assert r.returncode == 65, out(r)
    assert f"TIER REFUSED {tier} for {role}" in out(r)
    assert h.calls("run") == []


@slow
def test_o13_the_gate_may_run_heavy(h):
    h.results(1, f"pass {A}::test_x")
    r = h.run("--tier", "heavy", role="gate")
    assert r.returncode == 0, out(r)


# --- O14: the classifying rerun --------------------------------------------------------------

FAIL = f"failure {A}::test_x boom"
PASS = f"pass {A}::test_x"


@slow
def test_o14_a_failure_asked_again_on_the_same_tree_reruns_shuffled_and_a_pass_is_flaky(h):
    h.results(1, FAIL)
    h.results(2, PASS)
    first = h.run("--tier", "fast")
    assert first.returncode == 1, out(first)
    second = h.run("--tier", "fast")
    assert second.returncode == 1, out(second)          # never green
    assert "FLAKY" in out(second)
    runs = h.calls("run")
    assert len(runs) == 2, runs
    assert "--shuffle" not in runs[0] and "--shuffle" in runs[1], runs
    flakes = h.repo / ".work" / "runs" / "E9" / "flakes"
    assert flakes.is_file() and "FLAKY" in flakes.read_text(encoding="utf-8")
    assert [g["outcome"] for g in h.gates()][-1] == "flaky"


@slow
def test_o14_a_rerun_that_fails_again_is_not_recorded_flaky(h):
    h.results(1, FAIL)
    h.results(2, FAIL)
    h.run("--tier", "fast")
    second = h.run("--tier", "fast")
    assert second.returncode == 1, out(second)
    flakes = h.repo / ".work" / "runs" / "E9" / "flakes"
    assert not flakes.is_file() or "FLAKY" not in flakes.read_text(encoding="utf-8")


@slow
def test_o14_a_third_ask_on_that_tree_exits_65_repeat(h):
    h.results(1, FAIL)
    h.results(2, FAIL)
    h.run("--tier", "fast")
    h.run("--tier", "fast")
    third = h.run("--tier", "fast")
    assert third.returncode == 65, out(third)
    assert "REPEAT" in out(third)
    assert len(h.calls("run")) == 2


@slow
def test_o14_an_adapter_without_shuffle_reruns_unshuffled(h):
    h.results(1, FAIL)
    h.results(2, PASS)
    env = h.env(FAKE_CAPS="")
    h.run("--tier", "fast", env=env)
    second = h.run("--tier", "fast", env=env)
    assert "FLAKY" in out(second)
    assert all("--shuffle" not in c for c in h.calls("run")), h.calls("run")


# --- O15: failed ids until green, then one wider run -----------------------------------------

@slow
def test_o15_after_a_failure_a_wider_or_different_ask_on_changed_code_is_narrow(h):
    h.results(1, FAIL, f"pass {A}::test_y")
    assert h.run("--ids", f"{A}::test_x", f"{A}::test_y").returncode == 1
    h.change_tree()
    wider = h.run("--tier", "fast")
    assert wider.returncode == 65, out(wider)
    assert "NARROW: run --failed until green" in out(wider)
    other = h.run("--ids", f"{A}::test_y")                    # a pass is not a failed id
    assert other.returncode == 65, out(other)
    assert "NARROW" in out(other)
    assert len(h.calls("run")) == 1


@slow
def test_o15_failed_runs_the_recorded_ids_and_a_subset_is_admitted(h):
    h.results(1, FAIL, f"failure {A}::test_z boom", f"pass {A}::test_y")
    h.results(2, f"pass {A}::test_x")
    h.run("--tier", "fast")
    h.change_tree()
    sub = h.run("--ids", f"{A}::test_x")
    assert sub.returncode == 0, out(sub)
    assert f"{A}::test_x" in h.calls("run")[1]
    h.change_tree()
    failed = h.run("--failed")
    assert failed.returncode in (0, 1), out(failed)
    last = h.calls("run")[2]
    assert f"{A}::test_z" in last and f"{A}::test_y" not in last, last


@slow
def test_o15_once_the_failed_ids_pass_one_wider_run_is_admitted(h):
    h.results(1, FAIL)
    h.results(2, PASS)
    h.results(3, PASS, f"pass {A}::test_y")
    h.run("--tier", "fast")
    h.change_tree()
    assert h.run("--failed").returncode == 0
    h.change_tree()
    wider = h.run("--tier", "fast")
    assert wider.returncode == 0, out(wider)
    assert len(h.calls("run")) == 3


@slow
def test_o15_when_no_ids_could_be_read_the_same_selection_is_allowed_and_counts(h):
    h.results(1, exit_code=1)                           # the suite did not run: no results
    first = h.run("--tier", "fast")
    assert first.returncode == 2, out(first)
    assert h.gates()[-1]["outcome"] == "did not run"
    h.change_tree()
    again = h.run("--tier", "fast")
    assert again.returncode in (0, 1), out(again)
    assert len(h.calls("run")) == 2
    assert len(h.gates()) == 2


# --- O16: repeat and run limits --------------------------------------------------------------

def _pass_on_new_tree(h, n_runs, *args, **kw):
    codes = []
    for _ in range(n_runs):
        h.change_tree()
        codes.append(h.run(*args, **kw))
    return codes


@slow
def test_o16_the_repeat_limit_defaults_to_3_per_selection(h):
    rs = _pass_on_new_tree(h, 4, "--tier", "fast")
    assert [r.returncode for r in rs[:3]] == [0, 0, 0], [out(r) for r in rs]
    assert rs[3].returncode == 65, out(rs[3])
    assert "REPEAT" in out(rs[3])


@slow
def test_o16_the_ticket_run_limit_comes_from_config_and_counts_owner_and_test_designer(repo, tmp_path):
    h = Harness(repo, tmp_path, repeat="9", runs="3")
    codes = []
    for i, role in enumerate(["owner", "test-designer", "owner", "owner"]):
        h.change_tree()
        codes.append(h.run("--ids", f"{A}::test_{i}", role=role))
    assert [c.returncode for c in codes[:3]] == [0, 0, 0], [out(c) for c in codes]
    assert codes[3].returncode == 65, out(codes[3])
    assert "RUN LIMIT" in out(codes[3])


@slow
def test_o16_gate_and_suite_owner_runs_are_not_counted(repo, tmp_path):
    h = Harness(repo, tmp_path, repeat="1", runs="1")
    for role in ["gate", "gate", "suite-owner", "gate"]:
        h.change_tree()
        r = h.run("--tier", "fast", role=role)
        assert r.returncode == 0, (role, out(r))
    h.change_tree()
    assert h.run("--tier", "fast").returncode == 0           # the owner's first


@slow
def test_o16_limits_are_per_ticket(repo, tmp_path):
    h = Harness(repo, tmp_path, repeat="9", runs="1")
    assert h.run("--tier", "fast", ticket="E9-T1").returncode == 0
    h.change_tree()
    assert h.run("--tier", "fast", ticket="E9-T2").returncode == 0
    h.change_tree()
    assert h.run("--tier", "fast", ticket="E9-T1").returncode == 65


# --- O17: gates.jsonl ------------------------------------------------------------------------

@slow
def test_o17_a_run_appends_one_line_with_the_recorded_fields(h):
    h.results(1, f"pass {A}::test_x", f"pass {A}::test_y", f"failure {A}::test_z boom")
    r = h.run("--tier", "fast", "--workers", "2", role="test-designer", ticket="E9-T4")
    assert r.returncode == 1, out(r)
    lines = h.gates()
    assert len(lines) == 1, lines
    g = lines[0]
    for k in ("role", "ticket", "selection", "tree", "selected", "workers", "wall_s", "peak_gb", "exit", "outcome"):
        assert k in g, (k, g)
    assert (g["role"], g["ticket"], g["selection"]) == ("test-designer", "E9-T4", "fast")
    assert g["selected"] == 3 and g["workers"] == 2 and g["exit"] == 1 and g["outcome"] == "fail"
    assert isinstance(g["tree"], str) and g["tree"]
    assert isinstance(g["wall_s"], (int, float)) and g["wall_s"] >= 0
    assert isinstance(g["peak_gb"], (int, float)) and g["peak_gb"] >= 0


@slow
def test_o17_a_passing_run_and_a_refusal_are_recorded_too(h):
    h.results(1, PASS)
    assert h.run("--tier", "fast").returncode == 0
    assert h.run("--tier", "heavy").returncode == 65
    got = h.gates()
    assert [(g["exit"], g["outcome"]) for g in got] == [(0, "pass"), (65, "refused")], got
    assert got[1]["selection"] == "heavy"


@slow
def test_o17_a_run_that_did_not_run_is_recorded(h):
    h.results(1, exit_code=1)
    assert h.run("--tier", "fast").returncode == 2
    got = h.gates()
    assert [(g["exit"], g["outcome"]) for g in got] == [(2, "did not run")], got


def test_usage_errors_are_64(h):
    assert h.run().returncode == 64
    assert h.run("--tier", "fast", "--ids", f"{A}::t").returncode == 64
    assert h.run("--tier", "nonesuch").returncode == 64
