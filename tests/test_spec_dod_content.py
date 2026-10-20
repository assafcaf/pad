"""Redesign PR 4: the spec is the run's scope (references, protected paths, domains), and the
definition of done is set by the reference class, judged independently of the writer.

Content tests: the skill and workflow prose are the product.
"""
from __future__ import annotations

import re

SPEC = "claude/skills/spec/SKILL.md"
DOD = "claude/workflow/definition-of-done.md"


def section(text: str, heading: str) -> str:
    m = re.search(rf"^{re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert m, f"no section {heading!r}"
    return m.group(1)


def template(text: str) -> str:
    m = re.search(r"```markdown\n(.*?)^```", text, re.S | re.M)
    assert m, "no spec template"
    return m.group(1)


# --- /spec -------------------------------------------------------------------------------


def test_spec_template_sections_and_what_references_name(payload_text):
    t = template(payload_text(SPEC))
    for heading in ("## References", "## Protected paths", "## Domains", "## Non-goals"):
        assert heading in t, heading
    t = t.lower()
    refs = t.split("## references", 1)[1].split("\n## ", 1)[0]
    for kind in ("mock crop", "viewport", "outcome id", "repro", "baseline", "spike"):
        assert kind in refs, kind


def test_spec_protected_paths_name_the_strict_discipline(payload_text):
    t = template(payload_text(SPEC)).lower()
    prot = t.split("## protected paths", 1)[1].split("\n## ", 1)[0]
    assert "strict" in prot
    for kind in ("storage", "sync", "auth", "migration", "data model"):
        assert kind in prot, kind


def test_spec_domains_are_bullets_not_tasks(payload_text):
    t = template(payload_text(SPEC)).lower()
    dom = t.split("## domains", 1)[1].split("\n## ", 1)[0]
    assert "not tasks" in dom


def test_spec_outcomes_only_for_areas_whose_reference_is_tests(payload_text):
    text = payload_text(SPEC)
    assert "only for areas whose reference is tests" in text


def test_spec_size_table_has_a_spike_first_row(payload_text):
    rows = [l for l in payload_text(SPEC).splitlines() if l.startswith("| **")]
    assert any("Spike first" in r and "no reference" in r.lower() for r in rows)


def test_spec_is_the_runs_frozen_scope(payload_text):
    text = payload_text(SPEC)
    assert ".work/runs/<epic>/scope.md" in text
    assert "frozen" in text.lower()
    assert "scope gate" in text.lower()


def test_spec_links_references_rather_than_restating_them(payload_text):
    assert "reference, not paraphrase" in payload_text(SPEC).lower()


def test_spec_hands_off_to_tickets_in_the_same_session(payload_text):
    hand = section(payload_text(SPEC), "## 6. Hand off")
    assert "/tickets" in hand
    assert "same session" in hand
    assert "/batch-implement" not in hand


def test_spec_keeps_grill_mode_and_decision_records(payload_text):
    text = payload_text(SPEC)
    assert "**Grill mode**" in text
    assert "docs/decisions/NNNN-<slug>.md" in text


# --- definition of done ------------------------------------------------------------------


REFERENCE_CLASSES = ("Visual", "Contract tests", "Behaviour tests", "Reproduction",
                     "Golden / metric", "Human")


def class_table(text: str) -> list[str]:
    rows = [l for l in text.splitlines() if l.startswith("| **")]
    assert rows, "no reference-class table"
    return rows


def test_dod_table_has_every_reference_class_and_column(payload_text):
    rows = class_table(payload_text(DOD))
    for cls in REFERENCE_CLASSES:
        assert any(r.startswith(f"| **{cls}") for r in rows), cls
    header = next(l for l in payload_text(DOD).splitlines() if l.startswith("| Class"))
    for col in ("Who writes the reference", "Red proof", "Evidence at merge", "Judge"):
        assert col in header, col


def test_dod_contract_class_is_strict_and_behaviour_class_owner_writes_tests_first(payload_text):
    row = next(r for r in class_table(payload_text(DOD)) if r.startswith("| **Contract"))
    assert "strict" in row.lower()
    assert "test-designer" in row
    assert "protected" in row.lower()
    row = next(r for r in class_table(payload_text(DOD)) if r.startswith("| **Behaviour"))
    assert "owner" in row.lower()
    assert "first" in row.lower()


def test_dod_judge_is_independent_of_the_writer(payload_text):
    text = payload_text(DOD)
    assert "Nobody's opinion of the code enters into it" not in text
    assert "the writer's never" in text


def test_dod_lists_the_shared_merge_gate(payload_text):
    gate = section(payload_text(DOD), "## The merge gate").lower()
    for item in ("affected tests", "lint", "typecheck", "build", "weakened-tests.sh",
                 "protected-path guard", "evidence", "ledger", "run-log"):
        assert item in gate, item


def test_dod_drops_tiers_and_the_universal_two_agent_split(payload_text):
    text = payload_text(DOD).lower()
    assert not re.search(r"ticket tier|tier [0-9]|tiers? of ticket", text)
    assert "code-writer" not in text
    assert "small task" not in text


def test_dod_keeps_the_red_exit_code_distinction_as_item_2(payload_text):
    done = section(payload_text(DOD), "## A ticket is done when")
    item2 = re.search(r"^2\. (.*?)(?=^3\. )", done, re.S | re.M)
    assert item2 and "red" in item2.group(1).lower()
    assert "never ran" in item2.group(1)


def test_dod_no_reference_means_a_spike(payload_text):
    assert "spike" in payload_text(DOD).lower()
