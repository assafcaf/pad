"""O49: suite-design.md ships with PAD, PAD-owned, and cites only sources that exist here.

Content tests plus one install: the standard the suite owner reads on every start is a payload
file, so the installer and /pad-update carry it like any other workflow file.
"""
from __future__ import annotations

import re
import subprocess

import pytest

from conftest import BASH, PAYLOAD, ROOT

DESIGN = "claude/workflow/suite-design.md"


def test_o49_suite_design_is_shipped_from_the_payload_workflow_folder(payload_text):
    text = payload_text(DESIGN)
    assert text.startswith("# Suite design")
    for n in range(1, 12):
        assert re.search(rf"^## {n}\. ", text, re.M), f"no section {n}"


def test_o49_every_docs_path_it_cites_exists_in_this_repo(payload_text):
    text = payload_text(DESIGN)
    cited = set(re.findall(r"docs/[A-Za-z0-9_./-]+\.md", text))
    assert "docs/2026-10-20-test-suite-design-standards.md" in cited
    for path in sorted(cited):
        assert (ROOT / path).is_file(), f"cites {path}, which does not exist"


def test_o49_it_does_not_cite_the_old_research_folder(payload_text):
    assert "docs/research/" not in payload_text(DESIGN)


def test_o49_acceptance_tests_are_marked_by_file_name_not_by_a_directory(payload_text):
    assert "tests/acceptance/" not in payload_text(DESIGN)


def test_o49_it_says_it_is_pad_owned_and_extended_only_through_rules_and_plugins(payload_text):
    text = re.sub(r"\s+", " ", payload_text(DESIGN).replace("`", ""))
    assert "/pad-update replaces it" in text
    assert "rules" in text and "plugins" in text


@pytest.mark.slow
def test_o49_install_puts_suite_design_in_the_projects_workflow_folder(repo):
    r = subprocess.run(
        [BASH, (ROOT / "install.sh").as_posix(), "--project", repo.as_posix(), "--tracker", "local"],
        cwd=str(repo), capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    installed = repo / ".claude" / "workflow" / "suite-design.md"
    assert installed.is_file()
    assert installed.read_text(encoding="utf-8") == (PAYLOAD / DESIGN).read_text(encoding="utf-8")
