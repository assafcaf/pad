"""E1-T20: config.example.md describes surfaces, review cadence and resource classes."""
from __future__ import annotations

import re

CONFIG = "claude/workflow/config.example.md"
SKILL = "claude/skills/pad-run/SKILL.md"

SURFACE_COLUMNS = [
    "Surface", "Entry point", "Test drives it by", "Person looks by", "Automated check",
    "Preview start", "Ready when", "Restart when changed", "Cannot show",
    "Reference dir", "Render command", "Viewport",
]


def section(text: str, heading: str) -> str:
    """Body of the `## <heading>` section, up to the next `## ` heading."""
    m = re.search(r"^## " + re.escape(heading) + r"[ \t]*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert m, f"no '## {heading}' section"
    return m.group(1)


def header_cells(body: str) -> list[str]:
    for line in body.splitlines():
        if line.lstrip().startswith("|"):
            return [c.strip() for c in line.strip().strip("|").split("|")]
    raise AssertionError("no table in section")


def test_o32_config_has_surfaces_table_with_every_column(payload_text):
    body = section(payload_text(CONFIG), "Surfaces")
    assert header_cells(body) == SURFACE_COLUMNS


def test_o32_config_and_pad_run_no_longer_have_a_local_app(payload_text):
    assert not re.search(r"^## Local app", payload_text(CONFIG), re.M)
    assert "Local app" not in payload_text(SKILL)


def test_o32_review_cadence_defaults_to_per_wave_and_lists_the_options(payload_text):
    body = section(payload_text(CONFIG), "Review")
    assert re.search(r"Cadence:\**\s*`?per-wave`?", body)
    for option in ("after-first-wave", "per-wave", "end-only", "none"):
        assert option in body


def test_o45_serial_resources_table_has_a_class_column_and_explains_both_classes(payload_text):
    body = section(payload_text(CONFIG), "Serial resources")
    assert "Class" in header_cells(body)
    assert "automated" in body
    assert "operator-run" in body
    assert "review packet" in body.lower()
