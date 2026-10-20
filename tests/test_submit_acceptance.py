"""O28, O29, O31, O50: submit-acceptance.sh, the acceptance half of the submit check.

    submit-acceptance.sh files [--suite] --adapter <runner.sh> --test-paths "<paths>" <KEY> <epic> <head>
    submit-acceptance.sh grade --outcomes <file> --red-results <file> --head-results <file>
    submit-acceptance.sh verdicts <report file> <id>...

Each verb ends on `SUBMIT OK` / `SUBMIT FAIL <rule>: <detail>` (files, grade; exit 0 or 1) or
`VERDICT OK` / `VERDICT FAIL <why>` (verdicts). `grade` reads what the adapter's `results` verb
prints (`pass|failure|error|skipped <id> [<message>]`) for the red commit and for the ticket head,
and the test-designer's OUTCOMES lines `- <O>: <id>[, <id>] | expects: <text>`. `red-grade 0` means
the red commit did not report `failure` with the text; `red-grade 1` means the head did not pass.
No test here runs a test runner: the verbs decide from files and git.
"""
from __future__ import annotations

from pathlib import Path

from conftest import PAYLOAD, git

PYTEST = (PAYLOAD / "claude/workflow/runners/pytest.sh").as_posix()
VITEST = (PAYLOAD / "claude/workflow/runners/vitest.sh").as_posix()
KEY = "KAN-12"
ID = "tests/test_store_KAN_12.py::test_prefill"


def _commit(repo: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        git("add", rel, cwd=repo)
    git("commit", "-q", "-m", msg, cwd=repo)
    return git("rev-parse", "HEAD", cwd=repo)


def _files(run_script, repo, base, head, *, key=KEY, adapter=PYTEST, paths="tests/ src/", suite=False):
    extra = ["--suite"] if suite else []
    return run_script(
        "submit-acceptance.sh", "files", *extra, "--adapter", adapter, "--test-paths", paths,
        key, base, head, cwd=repo,
    )


def _last(r) -> str:
    lines = r.stdout.strip().splitlines()
    return lines[-1] if lines else ""


# --- O28: files in the test paths carry the ticket key -------------------------------------


def test_o28_test_file_named_with_the_key_passes(repo, run_script):
    base = git("rev-parse", "HEAD", cwd=repo)
    head = _commit(repo, {"tests/test_store_KAN_12.py": "def test_a():\n    assert False\n"}, "x")
    r = _files(run_script, repo, base, head)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == "SUBMIT OK"


def test_o28_key_written_with_a_dash_in_the_file_name_passes(repo, run_script):
    base = git("rev-parse", "HEAD", cwd=repo)
    head = _commit(repo, {"tests/test_store_KAN-12.py": "def test_a():\n    assert False\n"}, "x")
    r = _files(run_script, repo, base, head)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == "SUBMIT OK"


def test_o28_test_file_without_the_key_fails_tests_in_acceptance_with_its_path(repo, run_script):
    base = git("rev-parse", "HEAD", cwd=repo)
    head = _commit(repo, {"tests/test_store.py": "def test_a():\n    assert False\n"}, "x")
    r = _files(run_script, repo, base, head)
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r) == "SUBMIT FAIL tests-in-acceptance: tests/test_store.py"


def test_o28_file_named_for_another_ticket_fails(repo, run_script):
    base = git("rev-parse", "HEAD", cwd=repo)
    head = _commit(repo, {"tests/test_store_KAN_99.py": "def test_a():\n    assert False\n"}, "x")
    r = _files(run_script, repo, base, head)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "tests-in-acceptance: tests/test_store_KAN_99.py" in _last(r)


def test_o28_a_file_outside_the_test_paths_is_not_checked(repo, run_script):
    base = git("rev-parse", "HEAD", cwd=repo)
    head = _commit(repo, {"docs/notes.md": "x\n"}, "x")
    r = _files(run_script, repo, base, head, paths="tests/")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == "SUBMIT OK"


def test_o28_one_bad_file_among_good_ones_fails_and_names_the_bad_one(repo, run_script):
    base = git("rev-parse", "HEAD", cwd=repo)
    head = _commit(repo, {
        "tests/test_store_KAN_12.py": "def test_a():\n    assert False\n",
        "tests/sub/test_other.py": "def test_b():\n    assert False\n",
    }, "x")
    r = _files(run_script, repo, base, head)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "tests-in-acceptance: tests/sub/test_other.py" in _last(r)


def test_o28_a_suite_ticket_may_change_any_test_file(repo, run_script):
    base = git("rev-parse", "HEAD", cwd=repo)
    head = _commit(repo, {"tests/test_store.py": "def test_a():\n    assert True\n"}, "x")
    r = _files(run_script, repo, base, head, suite=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == "SUBMIT OK"


def test_o28_the_pattern_comes_from_the_adapter_vitest(repo, run_script):
    base = git("rev-parse", "HEAD", cwd=repo)
    good = _commit(repo, {"src/prefill.KAN-12.test.ts": "test('a', () => {})\n"}, "x")
    r = _files(run_script, repo, base, good, adapter=VITEST)
    assert r.returncode == 0, r.stdout + r.stderr
    bad = _commit(repo, {"src/prefill.test.ts": "test('a', () => {})\n"}, "y")
    r = _files(run_script, repo, good, bad, adapter=VITEST)
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r) == "SUBMIT FAIL tests-in-acceptance: src/prefill.test.ts"


# --- O29: the red grade ----------------------------------------------------------------------


def _grade(run_script, tmp_path, outcomes: str, red: str, head: str):
    for name, text in (("outcomes.txt", outcomes), ("red.txt", red), ("head.txt", head)):
        (tmp_path / name).write_text(text, encoding="utf-8")
    return run_script(
        "submit-acceptance.sh", "grade",
        "--outcomes", (tmp_path / "outcomes.txt").as_posix(),
        "--red-results", (tmp_path / "red.txt").as_posix(),
        "--head-results", (tmp_path / "head.txt").as_posix(),
        cwd=tmp_path,
    )


OUTCOMES = f"- O1: {ID} | expects: prefilled name\n"


def test_o29_failure_with_the_expected_text_then_pass_is_ok(tmp_path, run_script):
    r = _grade(run_script, tmp_path, OUTCOMES,
               f"failure {ID} AssertionError: prefilled name missing\n", f"pass {ID}\n")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == "SUBMIT OK"


def test_o29_error_at_red_is_red_grade_0(tmp_path, run_script):
    r = _grade(run_script, tmp_path, OUTCOMES,
               f"error {ID} ImportError: prefilled name\n", f"pass {ID}\n")
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r) == f"SUBMIT FAIL red-grade 0: {ID}"


def test_o29_failure_without_the_expected_text_is_red_grade_0(tmp_path, run_script):
    r = _grade(run_script, tmp_path, OUTCOMES,
               f"failure {ID} AssertionError: something else\n", f"pass {ID}\n")
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r) == f"SUBMIT FAIL red-grade 0: {ID}"


def test_o29_a_test_that_already_passes_at_red_is_red_grade_0(tmp_path, run_script):
    r = _grade(run_script, tmp_path, OUTCOMES, f"pass {ID}\n", f"pass {ID}\n")
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r) == f"SUBMIT FAIL red-grade 0: {ID}"


def test_o29_a_test_that_did_not_run_at_red_is_red_grade_0(tmp_path, run_script):
    r = _grade(run_script, tmp_path, OUTCOMES, "", f"pass {ID}\n")
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r) == f"SUBMIT FAIL red-grade 0: {ID}"


def test_o29_not_passing_at_the_head_is_red_grade_1(tmp_path, run_script):
    r = _grade(run_script, tmp_path, OUTCOMES,
               f"failure {ID} AssertionError: prefilled name missing\n",
               f"failure {ID} AssertionError: prefilled name missing\n")
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r) == f"SUBMIT FAIL red-grade 1: {ID}"


def test_o29_each_id_of_an_outcomes_line_is_graded_with_the_lines_text(tmp_path, run_script):
    other = "tests/test_store_KAN_12.py::test_second"
    r = _grade(
        run_script, tmp_path, f"- O1: {ID}, {other} | expects: prefilled name\n",
        f"failure {ID} AssertionError: prefilled name\nfailure {other} AssertionError: nope\n",
        f"pass {ID}\npass {other}\n",
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r) == f"SUBMIT FAIL red-grade 0: {other}"


# --- O31, O50: the VERDICT line --------------------------------------------------------------

V1 = "tests/test_a_KAN_12.py::test_one"
V2 = "tests/test_a_KAN_12.py::test_two"


def _verdicts(run_script, tmp_path, report: str, *ids: str):
    p = tmp_path / "report.txt"
    p.write_text(report, encoding="utf-8")
    return run_script("submit-acceptance.sh", "verdicts", p.as_posix(), *ids, cwd=tmp_path)


def _line(id_: str, verb: str = "promote", tier: str = "fast", why: str = "§3 asserts one behaviour") -> str:
    return f"VERDICT {KEY} {id_} {verb} {tier} — {why}\n"


def test_o31_one_wellformed_line_per_acceptance_test_is_ok(tmp_path, run_script):
    report = "notes\n" + _line(V1) + _line(V2, "retire", "heavy", "§9 duplicates test_one")
    r = _verdicts(run_script, tmp_path, report, V1, V2)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == "VERDICT OK"


def test_o31_a_test_without_a_line_fails_naming_it(tmp_path, run_script):
    r = _verdicts(run_script, tmp_path, _line(V1), V1, V2)
    assert r.returncode == 1, r.stdout + r.stderr
    assert V2 in r.stdout
    assert _last(r).startswith("VERDICT FAIL")


def test_o31_two_lines_for_one_test_fail(tmp_path, run_script):
    r = _verdicts(run_script, tmp_path, _line(V1) + _line(V1, "rewrite"), V1)
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r).startswith("VERDICT FAIL")
    assert V1 in r.stdout


def test_o31_a_verb_other_than_promote_rewrite_retire_fails(tmp_path, run_script):
    r = _verdicts(run_script, tmp_path, _line(V1, "keep"), V1)
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r).startswith("VERDICT FAIL")


def test_o31_a_line_without_a_tier_fails(tmp_path, run_script):
    bad = f"VERDICT {KEY} {V1} promote — §3 why\n"
    r = _verdicts(run_script, tmp_path, bad, V1)
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r).startswith("VERDICT FAIL")


def test_o31_a_line_without_a_reason_fails(tmp_path, run_script):
    r = _verdicts(run_script, tmp_path, f"VERDICT {KEY} {V1} promote fast\n", V1)
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r).startswith("VERDICT FAIL")


def test_o50_a_reason_that_cites_no_section_fails(tmp_path, run_script):
    r = _verdicts(run_script, tmp_path, _line(V1, why="it looked fine"), V1)
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r).startswith("VERDICT FAIL")


def test_o50_a_section_number_with_more_digits_is_cited(tmp_path, run_script):
    r = _verdicts(run_script, tmp_path, _line(V1, why="§10 per wave"), V1)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == "VERDICT OK"
