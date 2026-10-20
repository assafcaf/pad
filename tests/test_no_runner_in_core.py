"""E3-T3: the merge scripts carry no runner pattern of their own (O19).

merge-gate.sh and the helpers it sources read failures through the adapter's `results` verb, so
no line of them (outside a comment) names a runner or matches a runner's output or test-definition
pattern. (load-probe.sh and weakened-tests.sh are the runner domain's files; their own check is
not in this ticket's ownership.)
"""
from __future__ import annotations

import re

import pytest

from conftest import BIN

SCRIPTS = ["merge-gate.sh", "merge-lib.sh", "triage.sh"]
RUNNER_NAMES = re.compile(r"pytest|vitest|jest", re.I)
RUNNER_PATTERNS = re.compile(r"\^FAILED|def test_")


def code_lines(name: str):
    for i, line in enumerate((BIN / name).read_text(encoding="utf-8").splitlines(), 1):
        if not line.lstrip().startswith("#"):
            yield i, line


@pytest.mark.parametrize("name", SCRIPTS)
def test_o19_no_runner_name_outside_a_comment(name):
    found = [f"{name}:{i}: {l.strip()}" for i, l in code_lines(name) if RUNNER_NAMES.search(l)]
    assert found == []


@pytest.mark.parametrize("name", SCRIPTS)
def test_o19_no_runner_output_or_test_definition_pattern_outside_a_comment(name):
    found = [f"{name}:{i}: {l.strip()}" for i, l in code_lines(name) if RUNNER_PATTERNS.search(l)]
    assert found == []
