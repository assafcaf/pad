"""PAD 0.3.0: an installed 0.2.0 project is told how to upgrade, and the upgrade names every
change copying files cannot make (the two new allow rules, the new config rows).
"""
from __future__ import annotations

from conftest import PAYLOAD, ROOT

NOTE = "migrations/0002-rules-derived-files-gate-packages.md"
SETUP = "claude/skills/setup-workflow/SKILL.md"
RULES = ("Bash(bash .claude/workflow/bin/rules.sh *)",
         "Bash(bash .claude/workflow/bin/affected-tests.sh *)")


def _installed() -> str:
    return (PAYLOAD / "claude" / "workflow" / "VERSION").read_text(encoding="utf-8").strip()


def test_the_installed_version_is_0_3_0_or_later():
    assert tuple(int(x) for x in _installed().split(".")) >= (0, 3, 0)


def test_the_packages_carry_the_same_version():
    version = (ROOT / "payload" / "claude" / "workflow" / "VERSION").read_text(encoding="utf-8").strip()
    assert f'"version": "{version}"' in (ROOT / "package.json").read_text(encoding="utf-8")
    assert f'version = "{version}"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_a_0_2_0_config_fails_preflight_naming_the_upgrade_step(repo, run_script, tmp_path):
    # The rest of preflight is covered in test_preflight.py; this pins the 0.2.0 -> installed message.
    from test_preflight import config_md, failures, install

    install(repo, config=config_md(version="0.2.0"))
    home = tmp_path / "home"
    home.mkdir()
    r = run_script("preflight.sh", cwd=repo, env={"HOME": home.as_posix()})
    msgs = [d for c, d in failures(r) if c == "version"]
    assert msgs, r.stdout
    want = f"PAD version 0.2.0, older than the installed {_installed()}: run /setup-workflow upgrade"
    assert want in msgs[0]


def test_the_migration_note_names_both_allow_rules(payload_text):
    text = payload_text(NOTE)
    for rule in RULES:
        assert rule in text, rule


def test_the_migration_note_has_the_required_shape(payload_text):
    text = payload_text(NOTE)
    assert text.startswith("# 0002 — ")
    assert "Applies when:" in text and "## Steps" in text and "## Check" in text


def test_the_migration_note_leaves_settings_to_the_operator(payload_text):
    assert "the operator adds them to `.claude/settings.json`" in payload_text(NOTE)


def test_setup_upgrade_adds_missing_rows_and_names_the_allow_rules(payload_text):
    text = payload_text(SETUP)
    step = text[text.index("## 7f. Upgrade"):text.index("## 8.")]
    assert "row" in step and "config.example.md" in step
    assert "allow rule" in step
    assert "`commands`" in step
