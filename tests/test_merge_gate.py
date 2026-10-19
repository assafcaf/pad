"""O8: merge-gate.sh gates one commit of a candidate worktree and prints GATE PASS or GATE FAIL.

    merge-gate.sh --candidate <path> [--at <commit>] [--gate full|lint|<command>]

Run from the epic worktree (its HEAD is the epic head). The commands come from the config
table's rows `Setup in a fresh worktree`, `Full suite`, `Typecheck` and `Lint`, read from
`.claude/workflow/config.md`. The candidate is a detached worktree on the epic head with the
batch's commits on top. Fixture commands append to a log outside the repo, so a test asserts
which commands ran, in which order and where.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from conftest import git

pytestmark = pytest.mark.slow


def _config(log: Path, *, setup="true", full="true", typecheck="true", lint="true") -> str:
    def row(name: str, tag: str, cmd: str) -> str:
        return f'| {name} | `echo {tag} >> "{log.as_posix()}"; {cmd}` |\n'

    return (
        "## Commands\n\n| Command | Value |\n|---|---|\n"
        + row("Setup in a fresh worktree", "setup", setup)
        + row("Full suite", "gate", full)
        + row("Typecheck", "typecheck", typecheck)
        + row("Lint", "lint", lint)
    )


def _commit(wt: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        p = wt / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        git("add", rel, cwd=wt)
    git("commit", "-q", "-m", msg, cwd=wt)
    return git("rev-parse", "HEAD", cwd=wt)


class Env:
    def __init__(self, repo, worktree, run_script, tmp_path, **cmds):
        self.repo, self.run_script = repo, run_script
        self.log = tmp_path / "ran.log"
        self.epic = worktree(repo, "epic")
        self.epic_head = _commit(
            self.epic,
            {
                ".claude/workflow/config.md": _config(self.log, **cmds),
                "src/base.py": "BASE = 1\n",
                "tests/test_other.py": "from base import BASE\n",
            },
            "epic: base",
        )
        git("push", "-q", "-u", "origin", "epic", cwd=self.epic)
        self.cand = repo.parent / "cand"
        git("worktree", "add", "-q", "--detach", self.cand.as_posix(), self.epic_head, cwd=repo)

    def commit(self, files: dict[str, str], msg: str = "batch") -> str:
        return _commit(self.cand, files, msg)

    def gate(self, *args: str, env=None):
        return self.run_script(
            "merge-gate.sh", "--candidate", self.cand.as_posix(), *args, cwd=self.epic, env=env
        )

    def ran(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").split() if self.log.exists() else []


@pytest.fixture
def env(repo, worktree, run_script, tmp_path):
    def make(**cmds) -> Env:
        return Env(repo, worktree, run_script, tmp_path, **cmds)

    return make


def _last(r) -> str:
    lines = r.stdout.strip().splitlines()
    return lines[-1] if lines else ""


def test_green_candidate_prints_gate_pass_after_gate_typecheck_and_lint(env):
    e = env()
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate()
    assert _last(r) == "GATE PASS", r.stdout + r.stderr
    assert r.returncode == 0
    assert e.ran() == ["gate", "typecheck", "lint"]


def test_gate_runs_in_the_candidate_on_its_tree(env):
    e = env(full='grep -q "X = 1" src/impl.py')
    e.commit({"src/impl.py": "X = 1\n"})
    assert not (e.epic / "src" / "impl.py").exists()
    r = e.gate()
    assert _last(r) == "GATE PASS", r.stdout + r.stderr


def test_failing_gate_prints_its_output_tail_then_gate_fail(env):
    e = env(full="echo boom-marker; exit 1")
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate()
    assert _last(r) == "GATE FAIL", r.stdout + r.stderr
    assert r.returncode != 0
    assert "boom-marker" in r.stdout
    assert e.ran() == ["gate"]  # nothing after a red gate


def test_gate_output_is_a_tail_not_the_whole_log(env):
    e = env(full="seq 1 1000; exit 1")
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate()
    assert _last(r) == "GATE FAIL", r.stdout + r.stderr
    lines = r.stdout.split()
    assert "1000" in lines
    assert "2" not in lines


def test_failing_typecheck_is_gate_fail_with_its_output(env):
    e = env(typecheck="echo type-marker; exit 1")
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate()
    assert _last(r) == "GATE FAIL", r.stdout + r.stderr
    assert "type-marker" in r.stdout
    assert e.ran() == ["gate", "typecheck"]


def test_failing_lint_is_gate_fail_with_its_output(env):
    e = env(lint="echo lint-marker; exit 1")
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate()
    assert _last(r) == "GATE FAIL", r.stdout + r.stderr
    assert "lint-marker" in r.stdout
    assert e.ran() == ["gate", "typecheck", "lint"]


def test_at_gates_that_commit_not_the_candidate_head(env):
    e = env(full="test ! -f src/second.py")
    first = e.commit({"src/first.py": "A = 1\n"})
    e.commit({"src/second.py": "B = 1\n"})
    r = e.gate("--at", first)
    assert _last(r) == "GATE PASS", r.stdout + r.stderr
    r = e.gate()
    assert _last(r) == "GATE FAIL", r.stdout + r.stderr


def test_setup_runs_before_the_gate_when_a_manifest_changed(env):
    e = env()
    e.commit({"src/impl.py": "X = 1\n", "requirements.txt": "pytest\n"})
    r = e.gate()
    assert _last(r) == "GATE PASS", r.stdout + r.stderr
    assert e.ran() == ["setup", "gate", "typecheck", "lint"]


def test_setup_is_skipped_when_no_manifest_changed(env):
    e = env()
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate()
    assert _last(r) == "GATE PASS", r.stdout + r.stderr
    assert "setup" not in e.ran()


def test_setup_compares_the_gated_commit_not_the_candidate_head(env):
    e = env()
    first = e.commit({"src/impl.py": "X = 1\n"})
    e.commit({"package.json": "{}\n"})
    r = e.gate("--at", first)
    assert _last(r) == "GATE PASS", r.stdout + r.stderr
    assert "setup" not in e.ran()
    r = e.gate()
    assert _last(r) == "GATE PASS", r.stdout + r.stderr
    assert "setup" in e.ran()


def test_failing_setup_is_gate_fail_and_the_gate_does_not_run(env):
    e = env(setup="echo setup-marker; exit 1")
    e.commit({"src/impl.py": "X = 1\n", "package-lock.json": "{}\n"})
    r = e.gate()
    assert _last(r) == "GATE FAIL", r.stdout + r.stderr
    assert "setup-marker" in r.stdout
    assert e.ran() == ["setup"]


def test_gate_holds_a_merge_priority_suite_slot(env, tmp_path):
    seen = tmp_path / "waiting.txt"
    e = env(
        full='ls "$(git rev-parse --git-common-dir)/pad-locks/merge-waiting" > "%s"' % seen.as_posix()
    )
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate()
    assert _last(r) == "GATE PASS", r.stdout + r.stderr
    assert seen.read_text(encoding="utf-8").strip() != ""  # a merge-priority run was registered


# A failure sitting only in test files the batch neither changed nor imports ------------------


def _flaky(counter: Path, fail_times: int, failed_line: str) -> str:
    c = counter.as_posix()
    return (
        f'echo x >> "{c}"; n=$(wc -l < "{c}"); '
        f'if [ "$n" -le {fail_times} ]; then echo "{failed_line}"; exit 1; fi'
    )


def _runs(counter: Path) -> int:
    return len(counter.read_text(encoding="utf-8").split()) if counter.exists() else 0


def test_failure_only_in_unrelated_test_files_is_rerun_once_and_a_green_rerun_passes(env, tmp_path):
    n = tmp_path / "n.txt"
    e = env(full=_flaky(n, 1, "FAILED tests/test_other.py::test_x - boom"))
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate()
    assert _last(r) == "GATE PASS", r.stdout + r.stderr
    assert _runs(n) == 2


def test_failure_that_persists_in_unrelated_test_files_is_rerun_only_once(env, tmp_path):
    n = tmp_path / "n.txt"
    e = env(full=_flaky(n, 99, "FAILED tests/test_other.py::test_x - boom"))
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate()
    assert _last(r) == "GATE FAIL", r.stdout + r.stderr
    assert "tests/test_other.py::test_x" in r.stdout
    assert _runs(n) == 2


def test_failure_in_a_test_file_the_batch_changed_is_not_rerun(env, tmp_path):
    n = tmp_path / "n.txt"
    e = env(full=_flaky(n, 1, "FAILED tests/test_new.py::test_x - boom"))
    e.commit({"src/impl.py": "X = 1\n", "tests/test_new.py": "def test_x():\n    pass\n"})
    r = e.gate()
    assert _last(r) == "GATE FAIL", r.stdout + r.stderr
    assert _runs(n) == 1


def test_failure_in_a_test_file_importing_a_changed_file_is_not_rerun(env, tmp_path):
    n = tmp_path / "n.txt"
    e = env(full=_flaky(n, 1, "FAILED tests/test_other.py::test_x - boom"))
    e.commit({"src/base.py": "BASE = 2\n"})  # tests/test_other.py does `from base import BASE`
    r = e.gate()
    assert _last(r) == "GATE FAIL", r.stdout + r.stderr
    assert _runs(n) == 1


def test_failure_naming_no_test_file_is_not_rerun(env, tmp_path):
    n = tmp_path / "n.txt"
    e = env(full=_flaky(n, 1, "something broke"))
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate()
    assert _last(r) == "GATE FAIL", r.stdout + r.stderr
    assert _runs(n) == 1


# --gate full | lint | <command> --------------------------------------------------------------


def test_gate_full_runs_the_configured_full_suite(env):
    e = env(full="echo full-marker; exit 1")
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate("--gate", "full")
    assert _last(r) == "GATE FAIL", r.stdout + r.stderr
    assert "full-marker" in r.stdout


def test_gate_lint_uses_the_configured_lint_command_in_place_of_the_full_suite(env):
    e = env(full="exit 1")
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate("--gate", "lint")
    assert _last(r) == "GATE PASS", r.stdout + r.stderr
    assert "gate" not in e.ran()
    assert "lint" in e.ran()


def test_gate_command_runs_in_place_of_the_full_suite(env):
    e = env(full="exit 1")
    e.commit({"src/impl.py": "X = 1\n"})
    r = e.gate("--gate", "grep -q 'X = 1' src/impl.py")
    assert _last(r) == "GATE PASS", r.stdout + r.stderr
    assert "gate" not in e.ran()
    r = e.gate("--gate", "echo custom-marker; exit 1")
    assert _last(r) == "GATE FAIL", r.stdout + r.stderr
    assert "custom-marker" in r.stdout
