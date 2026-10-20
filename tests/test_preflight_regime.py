"""E3-T4 O37, O4, O11: preflight.sh validates `## Test regime` and the host.

O37: a repo's `## Test regime` may add to the managed values and tighten them, never remove or
relax one. The managed values: the per-test kill of the three tiers (fast 60, heavy 300, epic
900 seconds), `Repeat limit:` 3, `Ticket run limit:` 12 and `Flaky quarantine:` 8 tests, 7 days
(a repo may set lower numbers). A violation is `PREFLIGHT FAIL regime: <detail>` and the detail
names the key (`Per-test kill`, `Repeat limit`, `Ticket run limit`, `Flaky quarantine`, or the
removed tier). `Tiers: none` in place of the tiers table keeps today's gates.

O4: when `.claude/workflow/host.md` exists, preflight re-proves containment (the command in
PAD_SELF_TEST_CMD, else `pad-proc.sh self-test`); a failure is `PREFLIGHT FAIL host: <reason>`.
O11: the host.md line `Adapter extras:` lists the extras that work; any of `contract-fast`,
`contract-heavy`, `leak-check`, `mutation` missing from it is reported on one line
`PREFLIGHT NOTE adapter extras missing: <names>` that does not fail the run.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from conftest import PAYLOAD
from test_preflight import (  # noqa: F401
    CONFIG_EXAMPLE, assert_failed, config_md, failures, install, last, lines, preflight,
)

OK_SELF_TEST = "echo 'SELF-TEST containment ok process-group'"
BAD_SELF_TEST = "echo 'powershell is locked down: no job object'; exit 1"


def regime(*, repeat="3", runs="12", quarantine="8 tests, 7 days", kills=("60", "300", "900"),
           tiers=("fast", "heavy", "epic"), tiers_none=False) -> str:
    out = ["", "## Test regime", "", "- **Runner:** `pytest`"]
    if tiers_none:
        out.append("- **Tiers:** none")
    out += [
        f"- **Repeat limit:** {repeat}",
        f"- **Ticket run limit:** {runs}",
        f"- **Flaky quarantine:** {quarantine}",
        "- **Suite map:** `tests/MAP.md`",
        "",
    ]
    if not tiers_none:
        out += ["| Tier | Adapter selector | Per-test kill | Budget | Declared GB | Workers |",
                "|---|---|---|---|---|---|"]
        for name, kill in zip(("fast", "heavy", "epic"), kills):
            if name in tiers:
                out.append(f"| {name} | tests/{name} | {kill} | 5 min | 0.5 | 4 |")
        out.append("")
    return "\n".join(out)


def _install_with(repo: Path, section: str) -> Path:
    return install(repo, config=config_md() + "\n" + section)


# --- O37 ----------------------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.parametrize("kwargs, key", [
    ({"repeat": "5"}, "Repeat limit"),
    ({"runs": "20"}, "Ticket run limit"),
    ({"quarantine": "9 tests, 7 days"}, "Flaky quarantine"),
    ({"quarantine": "8 tests, 30 days"}, "Flaky quarantine"),
    ({"kills": ("120", "300", "900")}, "Per-test kill"),
    ({"kills": ("60", "300", "1800")}, "Per-test kill"),
], ids=["repeat", "runs", "quarantine-count", "quarantine-days", "fast-kill", "epic-kill"])
def test_o37_a_relaxed_managed_value_fails_with_the_key_named(repo, preflight, kwargs, key):
    _install_with(repo, regime(**kwargs))
    assert_failed(preflight(repo), "regime", key)


@pytest.mark.slow
def test_o37_a_tier_the_repo_removes_fails_naming_the_tier(repo, preflight):
    _install_with(repo, regime(tiers=("fast", "epic")))
    assert_failed(preflight(repo), "regime", "heavy")


@pytest.mark.slow
def test_o37_a_relaxed_value_fails_even_when_the_rest_is_tightened(repo, preflight):
    _install_with(repo, regime(repeat="2", runs="6", kills=("30", "300", "900"),
                               quarantine="4 tests, 3 days").replace(
        "| fast | tests/fast | 30 |", "| fast | tests/fast | 90 |"))
    assert_failed(preflight(repo), "regime", "Per-test kill")


@pytest.mark.slow
def test_o37_tightened_values_and_tiers_none_pass_but_a_relaxed_value_under_none_still_fails(
    repo, preflight
):
    _install_with(repo, regime(repeat="2", runs="6", quarantine="4 tests, 3 days",
                               kills=("30", "120", "600")))
    ok = preflight(repo)
    assert failures(ok) == [], ok.stdout
    assert last(ok) == "PREFLIGHT OK"
    # the same repo, relaxing a managed value while declaring Tiers: none
    cfg = repo / ".claude" / "workflow" / "config.md"
    cfg.write_text(config_md() + "\n" + regime(repeat="9", tiers_none=True), encoding="utf-8")
    assert_failed(preflight(repo), "regime", "Repeat limit")


@pytest.mark.slow
def test_o37_the_regime_section_config_example_ships_passes_its_own_check(repo, preflight):
    example = (PAYLOAD / CONFIG_EXAMPLE).read_text(encoding="utf-8").replace("\r\n", "\n")
    m = re.search(r"^## Test regime\n.*?(?=^## |\Z)", example, re.S | re.M)
    assert m, "config.example.md has no ## Test regime section"
    _install_with(repo, "\n" + m.group(0))
    result = preflight(repo)
    assert failures(result) == [], result.stdout
    assert last(result) == "PREFLIGHT OK"


# --- O4, O11 ------------------------------------------------------------------------------------


def _host_md(repo: Path, extras: str | None = None) -> None:
    text = "OS: windows\nMemory total: 16 GB\nMemory cap: 85%\nContainment: process-group\n"
    text += "Self-test: SELF-TEST containment ok process-group\n"
    if extras is not None:
        text += f"Adapter extras: {extras}\n"
    (repo / ".claude" / "workflow" / "host.md").write_text(text, encoding="utf-8")


def _run(run_script, tmp_path: Path, repo: Path, self_test: str):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return run_script("preflight.sh", cwd=repo,
                      env={"HOME": home.as_posix(), "PAD_SELF_TEST_CMD": self_test})


@pytest.mark.slow
def test_o4_a_failing_containment_self_test_fails_the_host_check_with_the_reason(
    repo, run_script, tmp_path
):
    install(repo)
    _host_md(repo)
    r = _run(run_script, tmp_path, repo, BAD_SELF_TEST)
    assert_failed(r, "host", "powershell is locked down")


@pytest.mark.slow
def test_o4_a_passing_self_test_leaves_the_host_check_green(repo, run_script, tmp_path):
    install(repo)
    _host_md(repo)
    r = _run(run_script, tmp_path, repo, OK_SELF_TEST)
    assert failures(r) == [], r.stdout
    assert last(r) == "PREFLIGHT OK"
    # and a failing one, on this same repo, does fail: the pass above is not vacuous
    assert failures(_run(run_script, tmp_path, repo, BAD_SELF_TEST)) != []


@pytest.mark.slow
def test_o11_preflight_lists_the_adapter_extras_that_are_missing_without_failing(
    repo, run_script, tmp_path
):
    install(repo)
    _host_md(repo, extras="contract-fast leak-check")
    r = _run(run_script, tmp_path, repo, OK_SELF_TEST)
    assert r.returncode == 0, r.stdout + r.stderr
    assert last(r) == "PREFLIGHT OK"
    notes = [l for l in lines(r) if l.startswith("PREFLIGHT NOTE adapter extras missing:")]
    assert len(notes) == 1, r.stdout
    assert "contract-heavy" in notes[0] and "mutation" in notes[0]
    assert "contract-fast" not in notes[0] and "leak-check" not in notes[0]


@pytest.mark.slow
def test_o11_no_note_when_every_extra_works(repo, run_script, tmp_path):
    install(repo)
    _host_md(repo, extras="contract-fast contract-heavy leak-check mutation")
    r = _run(run_script, tmp_path, repo, OK_SELF_TEST)
    assert r.returncode == 0, r.stdout + r.stderr
    assert not any("adapter extras" in l for l in lines(r)), r.stdout
    # but a host whose adapter has none says so
    _host_md(repo, extras="none")
    r2 = _run(run_script, tmp_path, repo, OK_SELF_TEST)
    notes = [l for l in lines(r2) if "adapter extras missing" in l]
    assert len(notes) == 1 and all(
        n in notes[0] for n in ("contract-fast", "contract-heavy", "leak-check", "mutation"))
