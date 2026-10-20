"""E3-T4 O4, O10, O11, O18, O43: /setup-workflow installs the test regime; migration 0005 brings an
installed repo up to it with `Tiers: none`.

Content tests read the prose that is the product (the skill, the migration note, the shipped
config and settings); the unit tests run preflight.sh on a repo that has the config example beside
its scripts, the way an installed repo does.
"""
from __future__ import annotations

import json
import re

import pytest

from conftest import PAYLOAD
from test_preflight import config_md, failures, install, last, preflight  # noqa: F401
from test_setup_content import sections

SKILL = "claude/skills/setup-workflow/SKILL.md"
SETTINGS = "claude/settings.example.json"
MIGRATION = "migrations/0005-test-regime.md"


def _flat(s: str) -> str:
    return " ".join(s.split())


def _section_with(payload_text, needle: str) -> str:
    """The body of the SKILL section that mentions `needle` (the first, by position)."""
    for _number, _title, body in sections(payload_text(SKILL)):
        if needle in body:
            return _flat(body)
    pytest.fail(f"no section of {SKILL} mentions {needle!r}")


# --- O4: setup stops on a failed containment self-test ---------------------------------------------


def test_o4_the_host_step_runs_host_setup_and_stops_with_the_reason_on_a_failed_self_test(
    payload_text,
):
    body = _section_with(payload_text, "host-setup.sh")
    assert "bash .claude/workflow/bin/host-setup.sh" in body
    assert re.search(r"self-test", body, re.I)
    assert re.search(r"\bstops?\b", body, re.I)
    assert re.search(r"reason", body, re.I)
    assert "`host` check" in body or "host check" in body, "preflight's host check is not named"


# --- O10: a runner PAD does not ship gets an adapter from the template ------------------------------


def test_o10_setup_writes_the_adapter_from_the_template_for_an_unshipped_runner(payload_text):
    body = _section_with(payload_text, "runners/TEMPLATE.sh")
    assert ".claude/pad-plugins/runners/<name>.sh" in body
    assert re.search(r"no shipped adapter|does not ship|not shipped|PAD ships", body, re.I)


def test_o10_the_adapter_is_accepted_only_after_its_self_test_with_four_fixture_tests(
    payload_text,
):
    body = _section_with(payload_text, "runners/TEMPLATE.sh")
    assert re.search(r"only after .*self-test .*pass", body, re.I), body
    assert re.search(r"fail(s|ing)? as an assertion|assertion failure", body, re.I)
    assert re.search(r"one that passes|a passing", body, re.I)
    assert re.search(r"import .*(fail|cannot).*`error`", body, re.I)
    assert re.search(r"`results` returns the failing (test's )?id", body, re.I)


# --- O18: deny the runner, allow pad-test.sh, and prove the pair ------------------------------------


def test_o18_setup_denies_each_runner_name_allows_pad_test_and_proves_the_pair(payload_text):
    body = _section_with(payload_text, "runner-names")
    assert re.search(r"den(y|ies)", body, re.I)
    assert "bash .claude/workflow/bin/pad-test.sh*" in body
    assert "check-moves.sh" in body
    assert "run-tests" in body, "the capability row is not named"


def test_o18_the_example_settings_allow_pad_test_to_agents(payload_text):
    allow = json.loads(payload_text(SETTINGS))["permissions"]["allow"]
    assert any(re.fullmatch(r"Bash\(bash \.claude/workflow/bin/pad-test\.sh ?\*\)", r) for r in allow), (
        [r for r in allow if "pad-test" in r])


# --- O11: the missing extras are listed where the operator reads ------------------------------------


def test_o11_setup_reports_the_missing_adapter_extras_in_the_pr_body(payload_text):
    text = _flat(payload_text(SKILL))
    assert "Adapter extras" in text
    for extra in ("contract-fast", "contract-heavy", "leak-check", "mutation"):
        assert extra in text, extra
    assert re.search(r"(pull request|PR) body", text, re.I)


def test_setup_offers_suite_bootstrap_and_the_optional_repo_lint_rules(payload_text):
    text = _flat(payload_text(SKILL))
    assert "/suite-bootstrap" in text
    assert "rules/optional" in text
    assert "scope-docs-updated" in text and "layout-as-declared" in text


# --- O43: migration 0005 ---------------------------------------------------------------------------


def test_o43_migration_0005_follows_the_note_format(payload_text):
    text = payload_text(MIGRATION)
    assert text.splitlines()[0].startswith("# 0005 — ")
    assert re.search(r"^Applies when:.*Test regime", text, re.M)
    assert "\n## Steps\n" in text and "\n## Check\n" in text


def test_o43_migrations_are_numbered_without_gaps():
    names = sorted(p.name[:4] for p in (PAYLOAD / "migrations").glob("[0-9][0-9][0-9][0-9]-*.md"))
    assert names == [f"{i:04d}" for i in range(1, len(names) + 1)]
    assert names[-1] == "0005"


def test_o43_the_note_adds_the_section_with_tiers_none_and_lists_the_protected_surface(
    payload_text,
):
    text = payload_text(MIGRATION)
    assert "## Test regime" in text
    assert "Tiers: none" in text
    for managed in (".claude/workflow/**", ".claude/settings.json", ".pre-commit-config.yaml"):
        assert managed in text, managed
    assert re.search(r"gates? (behave|behaves|run|stay)s? as before|unchanged", text, re.I)


def test_o43_the_note_leaves_settings_to_the_operator_and_names_the_rules_in_the_pr(payload_text):
    text = _flat(payload_text(MIGRATION))
    assert "pad-test.sh" in text
    assert re.search(r"pull request", text, re.I)
    assert not re.search(r"(write|edit|add to) `?\.claude/settings\.json`? (yourself|directly)", text, re.I)


@pytest.mark.slow
def test_o43_a_config_without_the_section_is_told_to_add_it_and_the_migrated_one_passes(
    repo, preflight
):
    """The installed workflow dir's config.example.md names the sections a config must have."""
    install(repo, config=config_md(omit=("Test regime",)))
    before = preflight(repo)
    assert any(c == "version" and "## Test regime" in d for c, d in failures(before)), before.stdout
    install_cfg = repo / ".claude" / "workflow" / "config.md"
    install_cfg.write_text(config_md(), encoding="utf-8")  # carries `Tiers: none`
    after = preflight(repo)
    assert failures(after) == [], after.stdout
    assert last(after) == "PREFLIGHT OK"
