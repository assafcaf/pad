"""O35, O36, O51, O34, O31: the prose of /suite-bootstrap, testing.md, the definition of done and
the brief template under the suite regime.

Content tests: these files are the product.
"""
from __future__ import annotations

import re

from conftest import PAYLOAD

SKILL_DIR = PAYLOAD / "claude" / "skills" / "suite-bootstrap"
TESTING = "claude/workflow/testing.md"
DOD = "claude/workflow/definition-of-done.md"
BRIEF = "claude/workflow/brief-template.md"


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", ""))


def skill_text() -> str:
    files = sorted(SKILL_DIR.rglob("*.md"))
    assert (SKILL_DIR / "SKILL.md") in files, "no suite-bootstrap/SKILL.md"
    return flat("\n".join(f.read_text(encoding="utf-8") for f in files))


# --- O35: /suite-bootstrap ---


def test_o35_skill_has_frontmatter_naming_the_skill():
    head = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1]
    assert "name: suite-bootstrap" in head


def test_o35_it_claims_the_host_exclusively():
    assert re.search(r"exclusive", skill_text(), re.I)
    assert "host" in skill_text()


def test_o35_it_dispatches_suite_owner_on_opus_once_per_phase_zero_to_eight():
    t = skill_text()
    assert "suite-owner" in t and "opus" in t
    assert "once per phase" in t
    for n in range(0, 9):
        assert f"Phase {n}" in t, f"Phase {n}"


def test_o35_phases_hand_off_through_the_work_suite_folder():
    assert ".work/suite/" in skill_text()


def test_o35_it_stops_after_phase_3_for_operator_review():
    t = skill_text()
    assert re.search(r"stop(s)? after (phase|Phase) 3", t)
    assert "operator" in t


def test_o35_it_ends_with_a_draft_pr_and_the_report_block():
    t = skill_text()
    assert "draft PR" in t
    assert "report block" in t.lower() or "Report" in t


def test_o35_every_test_run_goes_through_pad_test():
    t = skill_text()
    assert "pad-test.sh" in t
    assert re.search(r"(never|no|not) (run|start).{0,60}(runner|pytest|vitest) directly", t, re.I)


def test_o35_the_memory_cap_comes_from_host_md_not_config():
    t = skill_text()
    assert "host.md" in t


# --- O51: suite-design first, Phase 4b, Infrastructure line ---


def test_o51_the_suite_owner_reads_suite_design_first():
    t = skill_text()
    assert "suite-design.md" in t
    assert t.index("suite-design.md") < t.index("Phase 0")


def test_o51_phase_4b_follows_phase_4_and_builds_the_fixture_layer():
    t = skill_text()
    four = re.search(r"Phase 4(?!b)", t)
    assert four and four.start() < t.index("Phase 4b")
    assert t.index("Phase 4b") < t.index("Phase 5")
    assert "tests/_fixtures/" in t


def test_o51_the_fixture_readme_lists_cost_and_the_tiers_that_may_use_each_builder():
    t = skill_text()
    assert "tests/_fixtures/README.md" in t or "README.md" in t
    assert "one-time" in t and "per-copy" in t
    assert re.search(r"tiers? that may use", t)


def test_o51_the_fixture_layer_has_its_own_fast_tests():
    t = skill_text()
    assert re.search(r"(layer|fixtures?).{0,60}own .{0,10}fast tests", t)


def test_o51_the_report_carries_the_infrastructure_line():
    t = skill_text()
    assert "Infrastructure:" in t
    for part in ("collection", "fixture setups per run", "setup commands inside test bodies", "peak processes"):
        assert part in t, part


# --- O36: testing.md and the definition of done ---


def test_o36_testing_md_has_a_three_states_section_naming_acceptance_ci_and_dev(payload_text):
    text = payload_text(TESTING)
    m = re.search(r"^## Three states\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert m, "testing.md has no '## Three states' section"
    body = flat(m.group(1)).lower()
    for state in ("acceptance", "ci", "dev"):
        assert state in body, state
    assert "file name" in body


def test_o36_testing_md_runs_tests_only_through_pad_test(payload_text):
    assert "pad-test.sh" in flat(payload_text(TESTING))


def test_o36_an_epic_is_done_only_when_no_acceptance_named_file_remains(payload_text):
    t = flat(payload_text(DOD))
    assert re.search(r"no acceptance-named file remains", t)


def test_o36_an_epic_is_done_only_when_every_acceptance_test_has_a_verdict(payload_text):
    t = flat(payload_text(DOD))
    assert re.search(r"every acceptance test has a VERDICT", t)


def test_o36_an_epic_is_done_only_when_the_epic_tier_is_green(payload_text):
    t = flat(payload_text(DOD))
    assert re.search(r"epic tier is green", t)


# --- O34: the brief template ---


def test_o34_brief_template_carries_the_per_ticket_test_lines(payload_text):
    t = payload_text(BRIEF)
    assert "Expected to touch:" in t
    assert "Before READY:" in t
    assert "brief-tests.sh" in t
