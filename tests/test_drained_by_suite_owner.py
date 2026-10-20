"""O32: the test-removal rule drained-by-suite-owner explains a removed acceptance test only when
the removing commits belong to a suite ticket (subject `suite(<KEY>): ...`) and a
`VERDICT <KEY> <id> promote|rewrite|retire <tier> — <why>` line in a commit message of the range
names the test.

The rule's check is run as weakened-tests.sh runs it: `check.sh <base> <head> <removed-file>`,
the removed file holding `<path> TAB <name>` lines; it prints the lines it explains.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from conftest import BASH, PAYLOAD, git

RULES = PAYLOAD / "claude/workflow/rules"
FILE = "tests/test_x_KAN_12.py"
TWO = "def test_a():\n    assert True\n\n\ndef test_b():\n    assert True\n"
ONE_B = "def test_b():\n    assert True\n"


def _commit(repo: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        git("add", rel, cwd=repo)
    git("commit", "-q", "-m", msg, cwd=repo)
    return git("rev-parse", "HEAD", cwd=repo)


def _verdict(name: str, verb: str = "retire") -> str:
    return f"VERDICT KAN-12 {FILE}::{name} {verb} fast — §9 duplicates test_b"


def _removal(repo: Path, subject: str, body: str = "") -> tuple[str, str]:
    base = _commit(repo, {FILE: TWO}, "feat(KAN-12): the tests")
    msg = subject + (f"\n\n{body}" if body else "")
    head = _commit(repo, {FILE: ONE_B}, msg)
    return base, head


def _check(repo: Path, tmp_path: Path, base: str, head: str, removed: list[str]) -> list[str]:
    f = tmp_path / "removed.txt"
    f.write_text("".join(f"{FILE}\t{n}\n" for n in removed), encoding="utf-8")
    r = subprocess.run(
        [BASH, (RULES / "drained-by-suite-owner.sh").as_posix(), base, head, f.as_posix()],
        cwd=str(repo), capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    return sorted(ln.replace("\r", "") for ln in r.stdout.splitlines() if ln.strip())


def test_o32_a_suite_ticket_with_a_verdict_naming_the_test_explains_the_removal(repo, tmp_path):
    base, head = _removal(repo, "suite(E3-T9): drain KAN-12", _verdict("test_a"))
    assert _check(repo, tmp_path, base, head, ["test_a"]) == [f"{FILE}\ttest_a"]


def test_o32_a_rewrite_verdict_also_names_the_test(repo, tmp_path):
    base, head = _removal(repo, "suite(E3-T9): drain KAN-12", _verdict("test_a", "rewrite"))
    assert _check(repo, tmp_path, base, head, ["test_a"]) == [f"{FILE}\ttest_a"]


def test_o32_a_removal_by_a_non_suite_ticket_is_not_explained(repo, tmp_path):
    base, head = _removal(repo, "feat(KAN-13): tidy", _verdict("test_a"))
    assert _check(repo, tmp_path, base, head, ["test_a"]) == []


def test_o32_a_suite_ticket_without_a_verdict_does_not_explain_the_removal(repo, tmp_path):
    base, head = _removal(repo, "suite(E3-T9): drain KAN-12")
    assert _check(repo, tmp_path, base, head, ["test_a"]) == []


def test_o32_a_verdict_for_another_test_does_not_explain_this_one(repo, tmp_path):
    base, head = _removal(repo, "suite(E3-T9): drain KAN-12", _verdict("test_b"))
    assert _check(repo, tmp_path, base, head, ["test_a"]) == []


def test_o32_only_the_test_a_verdict_names_is_explained_of_two_removed(repo, tmp_path):
    base, head = _removal(repo, "suite(E3-T9): drain KAN-12", _verdict("test_a"))
    assert _check(repo, tmp_path, base, head, ["test_a", "test_b"]) == [f"{FILE}\ttest_a"]


def test_o32_weakened_tests_passes_a_drained_removal_and_fails_the_same_removal_by_a_feature(repo, run_script):
    base, head = _removal(repo, "suite(E3-T9): drain KAN-12", _verdict("test_a"))
    ok = run_script("weakened-tests.sh", base, head, cwd=repo)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "drained-by-suite-owner" in ok.stdout
    git("reset", "-q", "--hard", base, cwd=repo)
    head2 = _commit(repo, {FILE: ONE_B}, "feat(KAN-13): tidy\n\n" + _verdict("test_a"))
    bad = run_script("weakened-tests.sh", base, head2, cwd=repo)
    assert bad.returncode == 1, bad.stdout + bad.stderr


def test_o32_the_rule_file_is_a_test_removal_rule_with_a_warrant(run_script, repo):
    text = (RULES / "drained-by-suite-owner.md").read_text(encoding="utf-8")
    front = text.split("---", 2)[1]
    assert "name: drained-by-suite-owner" in front
    assert "kind: test-removal" in front
    assert "check: drained-by-suite-owner.sh" in front
    assert "warrant:" in front
    r = run_script("rules.sh", "list", "test-removal", cwd=repo)
    assert "drained-by-suite-owner" in r.stdout
