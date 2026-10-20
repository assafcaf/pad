"""E3-T3: /pad-run under the test regime (O26, O30, O53). Content tests: the skill's prose is the product."""
from __future__ import annotations

import re

from test_pad_run_content import SKILL, flat, section


def _epic_gate(text: str) -> str:
    m = re.search(r"^1\. \*\*Full gates\*\*(.*?)(?=^2\. \*\*)", section(text, "4. Finish the epic"), re.M | re.S)
    assert m, "section 4 has no step 1 (the epic gate)"
    return flat(m.group(1))


def _pause_paragraph(text: str) -> str:
    m = re.search(r"^\*\*Pause only when nothing is runnable\.\*\*(.*?)(?=^\*\*|^## )", text, re.M | re.S)
    assert m, "no 'Pause only when nothing is runnable' paragraph"
    return flat(m.group(1))


# --- O26: the epic gate runs every tier at the epic head -------------------------------------

def test_o26_the_epic_gate_runs_fast_heavy_and_epic_through_pad_test(payload_text):
    gate = _epic_gate(payload_text(SKILL))
    assert "pad-test.sh" in gate, gate
    for tier in ("fast", "heavy", "epic"):
        assert re.search(rf"--tier {tier}\b", gate), f"epic gate does not run --tier {tier}: {gate}"


def test_o26_the_epic_gate_still_runs_lint_and_typecheck(payload_text):
    gate = _epic_gate(payload_text(SKILL))
    assert re.search(r"\blint\b", gate, re.I) and re.search(r"\btypecheck\b", gate, re.I), gate


def test_o26_the_epic_tier_runs_beyond_the_epic_gate_are_the_orchestrators_call(payload_text):
    text = flat(payload_text(SKILL))
    assert re.search(r"epic tier[^.]*(your call|your decision|you decide)", text, re.I), \
        "the skill does not say that the other epic-tier runs are the orchestrator's call"


# --- O30: one suite ticket per wave that added acceptance tests ------------------------------

def test_o30_a_wave_that_added_acceptance_tests_dispatches_one_suite_ticket_to_suite_owner(payload_text):
    text = payload_text(SKILL)
    flat_text = flat(text)
    assert re.search(r"-suite-<n>", flat_text), "no `<epic key>-suite-<n>` ticket name"
    assert re.search(r"^\| `suite-owner` \|", text, re.M), "suite-owner is not in the agents table"
    m = re.search(r"[^.]*-suite-<n>[^.]*\.", flat_text)
    assert m and "suite-owner" in m.group(0) and "sonnet" in m.group(0), m and m.group(0)


def test_o30_the_suite_ticket_runs_in_parallel_with_the_next_wave(payload_text):
    flat_text = flat(payload_text(SKILL))
    assert re.search(r"suite ticket[^.]*in parallel with the next wave", flat_text, re.I), "no suite ticket in parallel with the next wave"


def test_o30_a_wave_with_no_acceptance_tests_dispatches_nothing(payload_text):
    flat_text = flat(payload_text(SKILL))
    assert re.search(r"(no|without) acceptance tests?[^.]*(dispatch(es)? nothing|no suite ticket)", flat_text, re.I), \
        "the skill does not say a wave with no acceptance tests dispatches nothing"


# --- O53: a pause or the end stops the watchdog and sweeps -----------------------------------

def test_o53_the_run_starts_the_watchdog(payload_text):
    flat_text = flat(payload_text(SKILL))
    assert re.search(r"cap-watch\.sh <run id>|cap-watch\.sh --run|start[^.]*cap-watch\.sh", flat_text), \
        "the skill never starts cap-watch.sh"


def test_o53_a_pause_stops_the_watchdog_and_sweeps(payload_text):
    para = _pause_paragraph(payload_text(SKILL))
    assert "cap-watch" in para, para
    assert re.search(r"\bsweep", para), para


def test_o53_the_end_of_the_run_stops_the_watchdog_and_sweeps(payload_text):
    text = payload_text(SKILL)
    end = flat(section(text, "4. Finish the epic"))
    assert "cap-watch" in end, end
    assert re.search(r"\bsweep", end), end


def test_o53_what_was_swept_is_logged_as_swept_n_processes(payload_text):
    assert "SWEPT <n> processes" in flat(payload_text(SKILL))
