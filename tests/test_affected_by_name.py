"""O30, O31: affected selects tests that name a changed file; merge-gate.sh --gate affected.

O30: a test file that names a changed file by file name (or its last two path components)
without importing it is selected by affected-tests.sh.
O31: merge-gate.sh --gate affected runs the Run named tests command on that selection, or the
full suite on FULL, and says which on a `gate:` line.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from conftest import git

pytestmark = pytest.mark.slow


def _commit(wt: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        p = wt / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        git("add", rel, cwd=wt)
    git("commit", "-q", "-m", msg, cwd=wt)
    return git("rev-parse", "HEAD", cwd=wt)


BASE_FILES = {
    "bin/merge-task.sh": "echo merge\n",
    "skills/pad-run/SKILL.md": "# pad-run\n",
    "skills/other/SKILL.md": "# other\n",
    "bin/unrelated.sh": "echo u\n",
    "tests/test_runs_script.py": (
        'import subprocess\n\n\ndef test_it():\n    subprocess.run(["bash", "bin/merge-task.sh"])\n'
    ),
    "tests/test_reads_text.py": (
        'from pathlib import Path\n\n\ndef test_it():\n    Path("skills/pad-run/SKILL.md").read_text()\n'
    ),
    "tests/test_unrelated.py": "def test_it():\n    assert True\n",
    "tests/test_near_miss.py": 'X = "my-merge-task.sh.bak and merge-task.shx"\n',
}


def _select(run_script, repo, changes):
    base = _commit(repo, BASE_FILES, "base")
    head = _commit(repo, changes, "change")
    r = run_script("affected-tests.sh", base, head, "--test-paths", "tests/", cwd=repo)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip().splitlines()[-1]


def test_o30_a_test_that_runs_a_changed_script_is_selected(run_script, repo):
    last = _select(run_script, repo, {"bin/merge-task.sh": "echo merge2\n"})
    assert last == "TESTS tests/test_runs_script.py"


def test_o30_a_test_that_reads_a_changed_text_is_selected(run_script, repo):
    last = _select(run_script, repo, {"skills/pad-run/SKILL.md": "# pad-run 2\n"})
    assert last.startswith("TESTS ")
    assert "tests/test_reads_text.py" in last.split()
    assert "tests/test_unrelated.py" not in last.split()


def test_o30_a_change_nobody_names_is_not_selected_by_name(run_script, repo):
    last = _select(run_script, repo, {"bin/unrelated.sh": "echo u2\n"})
    assert last.startswith("FULL")


# --- O31


def _config(log: Path) -> str:
    def row(name: str, cmd: str) -> str:
        return f"| {name} | `{cmd}` |\n"

    named_cmd = f'echo "named {{tests}}" >> "{log.as_posix()}"'
    return (
        "## Commands\n\n| Command | Value |\n|---|---|\n"
        + row("Full suite", f'echo full >> "{log.as_posix()}"')
        + row("Run named tests", named_cmd)
        + row("Typecheck", "true")
        + row("Lint", "true")
        + row("Test paths", "tests/")
    )


@pytest.fixture
def gate_env(repo, worktree, run_script, tmp_path):
    log = tmp_path / "ran.log"
    epic = worktree(repo, "epic")
    _commit(epic, {".claude/workflow/config.md": _config(log), **BASE_FILES}, "epic base")
    git("push", "-q", "-u", "origin", "epic", cwd=epic)
    cand = repo.parent / "cand"
    git("worktree", "add", "-q", "--detach", cand.as_posix(), "HEAD", cwd=epic)

    def go(changes):
        _commit(cand, changes, "batch")
        r = run_script("merge-gate.sh", "--candidate", cand.as_posix(), "--gate", "affected", cwd=epic)
        ran = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        return r, ran

    return go


def test_o31_affected_gate_runs_named_tests_on_the_selection(gate_env):
    r, ran = gate_env({"bin/merge-task.sh": "echo merge2\n"})
    lines = r.stdout.strip().splitlines()
    assert lines[-1] == "GATE PASS", r.stdout + r.stderr
    assert "gate: affected (tests/test_runs_script.py)" in lines
    assert ran == ["named tests/test_runs_script.py"]


def test_o31_affected_gate_runs_the_full_suite_when_the_selector_says_full(gate_env):
    r, ran = gate_env({"bin/unrelated.sh": "echo u2\n"})
    lines = r.stdout.strip().splitlines()
    assert lines[-1] == "GATE PASS", r.stdout + r.stderr
    assert any(line.startswith("gate: full (") for line in lines)
    assert ran == ["full"]
