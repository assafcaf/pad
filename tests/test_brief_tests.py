"""O34: brief-tests.sh <ticket> prints the two per-ticket lines /pad-run adds to the brief.

    brief-tests.sh [--map <file>] <ticket file>

    Expected to touch: <test files, comma-separated>
    Before READY: <pad-test forms>

The suite map is `--map`, else the config's `Suite map:` (under `## Test regime`), else
tests/MAP.md. A map line is `<source path>: <test file>[, <test file>...]`; a ticket's Owns path
and a map path match when one is the other or lies below it. The ticket's key is its file name.
"""
from __future__ import annotations

from pathlib import Path

TICKET = """## Outcome
Do the thing.

## Domain
suite

## Owns
- src/store.py
- src/db/

## Touches
none

## Protected
no
"""

MAP = """# Suite map
src/store.py: tests/test_store.py, tests/test_store_more.py
src/db/conn.py: tests/test_conn.py
src/other.py: tests/test_other.py
"""


def _ticket(tmp_path: Path) -> Path:
    p = tmp_path / "E9-T1.md"
    p.write_text(TICKET, encoding="utf-8")
    return p


def _map(repo: Path, text: str, name: str = "tests/MAP.md") -> None:
    p = repo / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _line(r, prefix: str) -> str:
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith(prefix)]
    assert len(lines) == 1, r.stdout + r.stderr
    return lines[0].rstrip("\r")


def _files(line: str) -> set[str]:
    return {f.strip() for f in line.split(":", 1)[1].split(",") if f.strip()}


def test_o34_expected_to_touch_lists_the_mapped_tests_of_the_owned_paths(repo, run_script, tmp_path):
    _map(repo, MAP)
    r = run_script("brief-tests.sh", _ticket(tmp_path).as_posix(), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _files(_line(r, "Expected to touch:")) == {
        "tests/test_store.py", "tests/test_store_more.py", "tests/test_conn.py",
    }


def test_o34_before_ready_names_the_pad_test_forms_for_the_ticket(repo, run_script, tmp_path):
    _map(repo, MAP)
    r = run_script("brief-tests.sh", _ticket(tmp_path).as_posix(), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    line = _line(r, "Before READY:")
    assert "pad-test.sh" in line
    assert "--tier fast" in line
    assert "--acceptance E9-T1" in line


def test_o34_the_map_file_is_the_one_named_in_config(repo, run_script, tmp_path):
    _map(repo, "## Test regime\n\n- Runner: `pytest`\n- Suite map: `custom/MAP.md`\n",
         ".claude/workflow/config.md")
    _map(repo, "src/store.py: tests/test_custom.py\n", "custom/MAP.md")
    _map(repo, MAP)
    r = run_script("brief-tests.sh", _ticket(tmp_path).as_posix(), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _files(_line(r, "Expected to touch:")) == {"tests/test_custom.py"}


def test_o34_map_flag_overrides_the_default(repo, run_script, tmp_path):
    m = tmp_path / "m.md"
    m.write_text("src/db/: tests/test_db_dir.py\n", encoding="utf-8")
    _map(repo, MAP)
    r = run_script("brief-tests.sh", "--map", m.as_posix(), _ticket(tmp_path).as_posix(), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _files(_line(r, "Expected to touch:")) == {"tests/test_db_dir.py"}


def test_o34_a_missing_map_still_prints_both_lines(repo, run_script, tmp_path):
    r = run_script("brief-tests.sh", _ticket(tmp_path).as_posix(), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _line(r, "Expected to touch:")
    assert "--acceptance E9-T1" in _line(r, "Before READY:")


def test_o34_a_ticket_file_that_does_not_exist_is_a_usage_error(repo, run_script, tmp_path):
    r = run_script("brief-tests.sh", (tmp_path / "nope.md").as_posix(), cwd=repo)
    assert r.returncode == 64, r.stdout + r.stderr
