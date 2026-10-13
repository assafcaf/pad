"""gate=affected: the merge gate runs only the tests the change reaches through imports.

    affected-tests.sh <base> <head> [--test-paths "<pathspecs>"]

Last line: `TESTS <file> ...` (changed test files, plus test files importing a changed module
directly or through other modules), or `FULL <reason>` when the full suite must run: a
conftest.py, manifest or lockfile changed, a non-test file under the test paths changed (a
helper), or nothing was selected.
"""
from __future__ import annotations

from pathlib import Path

from conftest import git


def _commit(wt: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        p = wt / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        git("add", rel, cwd=wt)
    git("commit", "-q", "-m", msg, cwd=wt)
    return git("rev-parse", "HEAD", cwd=wt)


BASE_FILES = {
    "pkg/core.py": "def f():\n    return 1\n",
    "pkg/api.py": "from pkg.core import f\n\n\ndef g():\n    return f()\n",
    "pkg/other.py": "Z = 1\n",
    "tests/test_core.py": "from pkg.core import f\n\n\ndef test_f():\n    assert f() == 1\n",
    "tests/test_api.py": "from pkg.api import g\n\n\ndef test_g():\n    assert g() == 1\n",
    "tests/test_other.py": "from pkg.other import Z\n\n\ndef test_z():\n    assert Z == 1\n",
}


def _run(run_script, repo, changes: dict[str, str]):
    base = _commit(repo, BASE_FILES, "base")
    head = _commit(repo, changes, "change")
    r = run_script("affected-tests.sh", base, head, "--test-paths", "tests/", cwd=repo)
    return r, r.stdout.strip().splitlines()[-1]


def test_a_changed_module_selects_its_direct_and_transitive_tests(run_script, repo):
    r, last = _run(run_script, repo, {"pkg/core.py": "def f():\n    return 1  # same\n"})
    assert r.returncode == 0, r.stderr
    assert last.startswith("TESTS ")
    assert set(last.split()[1:]) == {"tests/test_core.py", "tests/test_api.py"}


def test_a_changed_test_file_selects_itself(run_script, repo):
    _, last = _run(run_script, repo, {"tests/test_other.py": BASE_FILES["tests/test_other.py"] + "\n"})
    assert set(last.split()[1:]) == {"tests/test_other.py"}


def test_a_conftest_change_forces_the_full_suite(run_script, repo):
    _, last = _run(run_script, repo, {"tests/conftest.py": "X = 1\n"})
    assert last.startswith("FULL ") and "conftest.py" in last


def test_a_manifest_change_forces_the_full_suite(run_script, repo):
    _, last = _run(run_script, repo, {"pyproject.toml": "[project]\nname = 'x'\n"})
    assert last.startswith("FULL ") and "pyproject.toml" in last


def test_a_test_helper_change_forces_the_full_suite(run_script, repo):
    _, last = _run(run_script, repo, {"tests/helpers.py": "def h():\n    return 0\n"})
    assert last.startswith("FULL ") and "tests/helpers.py" in last


def test_a_change_no_test_reaches_runs_the_full_suite(run_script, repo):
    _, last = _run(run_script, repo, {"docs/notes.md": "notes\n"})
    assert last.startswith("FULL ")
