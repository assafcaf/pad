"""E3-T8: one reader (`regime.sh get <Key>`) for every `## Test regime` value."""
from __future__ import annotations

import re
import subprocess

import pytest

from conftest import BASH, BIN

READER = BIN / "regime.sh"
READERS = ("submit-acceptance.sh", "pad-test.sh", "check-moves.sh", "merge-gate.sh",
           "brief-tests.sh", "submit-surface.sh", "preflight.sh")


def _get(tmp_path, body: str, key: str = "Runner", crlf: bool = False):
    cfg = tmp_path / "config.md"
    text = body if crlf is False else body.replace("\n", "\r\n")
    cfg.write_bytes(text.encode())
    return subprocess.run([BASH, str(READER), "get", key, "--config", str(cfg)],
                          capture_output=True, text=True, timeout=60)


def _regime(*lines: str) -> str:
    return "# Config\n\n## Other\n\n- Runner: decoy\n\n## Test regime\n\n" + "\n".join(lines) + "\n\n## After\n\nRunner: decoy2\n"


@pytest.mark.parametrize("line,want", [
    ("- **Runner:** `pytest`. The adapter name: `runners/<name>.sh`.", "pytest"),
    ("- Runner: pytest", "pytest"),
    ("Runner: `vitest`", "vitest"),
])
def test_f1_get_prints_the_bare_value_in_every_documented_form(tmp_path, line, want):
    r = _get(tmp_path, _regime(line))
    assert (r.returncode, r.stdout.strip()) == (0, want), r.stderr


def test_f1_get_prints_only_the_value_and_strips_carriage_returns(tmp_path):
    r = _get(tmp_path, _regime("- **Runner:** `pytest`. prose"), crlf=True)
    assert r.stdout == "pytest\n", repr(r.stdout)


def test_f1_get_reads_another_key_such_as_repeat_limit(tmp_path):
    r = _get(tmp_path, _regime("- **Tiers:** none. x", "- **Repeat limit:** `3`. Runs of one."),
             key="Repeat limit")
    assert (r.returncode, r.stdout.strip()) == (0, "3"), r.stderr


@pytest.mark.parametrize("line", [
    "- **Runner:** `none`. The adapter name: `runners/<name>.sh`.",
    "- Runner: none",
    "Runner: `none`",
])
def test_f2_runner_none_prints_nothing_and_exits_0(tmp_path, line):
    r = _get(tmp_path, _regime(line))
    assert (r.returncode, r.stdout) == (0, ""), r.stderr


def test_f2_absent_runner_prints_nothing_and_exits_0(tmp_path):
    r = _get(tmp_path, _regime("- **Tiers:** none. x"))
    assert (r.returncode, r.stdout) == (0, ""), r.stderr


def test_f2_config_without_a_test_regime_section_prints_nothing_and_exits_0(tmp_path):
    r = _get(tmp_path, "# Config\n\n## Other\n\n- Runner: pytest\n")
    assert (r.returncode, r.stdout) == (0, ""), r.stderr


def test_f4_only_regime_sh_parses_the_test_regime_section():
    offenders = []
    for p in sorted(BIN.glob("*")):
        if p.name == "regime.sh" or not p.is_file():
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            code = line.strip()
            if code.startswith("#"):
                continue
            if re.search(r"Test regime", code) and re.search(r"\b(awk|sed|grep)\b", code):
                offenders.append(f"{p.name}:{n}")
    assert offenders == []


@pytest.mark.parametrize("name", READERS)
def test_f4_scripts_that_read_the_regime_go_through_regime_sh(name):
    text = (BIN / name).read_text(encoding="utf-8", errors="replace")
    assert "regime.sh" in text
