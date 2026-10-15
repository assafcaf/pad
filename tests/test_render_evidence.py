"""O7: render-evidence.sh writes the evidence file, logs the run line and prints the PR row."""
from pathlib import Path

RUN = "E1-20260929"
RED = "1111111aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
MERGE = "2222222bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def args(**over):
    base = {
        "run": RUN, "key": "E1-T9", "red": RED, "merge": MERGE, "outcomes": "O3 O4",
        "red-result": "pytest -q t -> 2 failed (exit 1)",
        "green-result": "pytest -q tests -> 40 passed (exit 0)",
    }
    base.update(over)
    out = []
    for k, v in base.items():
        if v is not None:
            out += [f"--{k}", v]
    return out


def evidence(main: Path, key="E1-T9", run=RUN) -> Path:
    return main / ".work" / "runs" / run / f"{key}.md"


def progress(main: Path, run=RUN) -> Path:
    return main / ".work" / "runs" / run / "progress.md"


def test_o7_writes_evidence_logs_the_run_line_and_prints_the_pr_row(repo, run_script):
    result = run_script("render-evidence.sh", *args(), cwd=repo)

    assert result.returncode == 0, result.stderr
    # the evidence file: shas, outcomes and gate results
    text = evidence(repo).read_text(encoding="utf-8")
    assert "E1-T9" in text
    assert RED in text and MERGE in text
    assert "O3 O4" in text
    assert "pytest -q t -> 2 failed (exit 1)" in text
    assert "pytest -q tests -> 40 passed (exit 0)" in text
    # the run-log line, with seven-char shas
    assert progress(repo).read_text(encoding="utf-8") == "E1-T9: done (red 1111111, merge 2222222)\n"
    # stdout: the run-log line, then the PR row as the last line
    lines = result.stdout.rstrip("\n").split("\n")
    assert lines[-1] == "| E1-T9 | O3 O4 | 2222222 |"
    assert "E1-T9: done (red 1111111, merge 2222222)" in lines[:-1]
    # optional flags omitted leave no trace of themselves
    assert "None" not in result.stdout


def test_o7_from_linked_worktree_writes_into_main_checkout(repo, worktree, run_script):
    wt = worktree(repo, "E1-T9")

    result = run_script("render-evidence.sh", *args(), cwd=wt)

    assert result.returncode == 0, result.stderr
    assert evidence(repo).is_file()
    assert progress(repo).is_file()
    assert not (wt / ".work").exists()


def test_o7_files_outside_and_rulings_appear_when_given(repo, run_script):
    result = run_script(
        "render-evidence.sh",
        *args(**{"files-outside": "docs/x.md tests/y.py", "rulings": "kept wording as is"}),
        cwd=repo,
    )

    assert result.returncode == 0, result.stderr
    text = evidence(repo).read_text(encoding="utf-8")
    assert "docs/x.md tests/y.py" in text
    assert "kept wording as is" in text


def test_o7_values_are_written_literally_without_expansion(repo, run_script):
    weird = "echo $HOME `whoami` 50% \\t -> ok"

    result = run_script("render-evidence.sh", *args(**{"green-result": weird}), cwd=repo)

    assert result.returncode == 0, result.stderr
    assert weird in evidence(repo).read_text(encoding="utf-8")


def test_o7_second_task_adds_its_own_file_and_log_line(repo, run_script):
    assert run_script("render-evidence.sh", *args(), cwd=repo).returncode == 0
    other = args(key="E1-T10", merge="3333333ccccccccccccccccccccccccccccccccc", outcomes="O9")
    result = run_script("render-evidence.sh", *other, cwd=repo)

    assert result.returncode == 0, result.stderr
    assert evidence(repo, "E1-T9").is_file() and evidence(repo, "E1-T10").is_file()
    assert progress(repo).read_text(encoding="utf-8").splitlines() == [
        "E1-T9: done (red 1111111, merge 2222222)",
        "E1-T10: done (red 1111111, merge 3333333)",
    ]
    assert result.stdout.rstrip("\n").split("\n")[-1] == "| E1-T10 | O9 | 3333333 |"


def test_o7_bad_arguments_are_a_usage_error_and_write_nothing(repo, run_script):
    calls = {"no-arguments": [], "unknown-flag": [*args(), "--bogus", "x"]}
    for missing in ["run", "key", "red", "merge", "outcomes", "red-result", "green-result"]:
        calls[f"missing --{missing}"] = args(**{missing: None})
    for name, argv in calls.items():
        result = run_script("render-evidence.sh", *argv, cwd=repo)

        assert result.returncode == 64, name
        assert not (repo / ".work").exists(), name


def test_o7_merge_task_records_finished_tasks_with_the_script(payload_text):
    # The merge writes its own evidence; the orchestrator writes none of it again.
    assert "render-evidence.sh" in payload_text("claude/workflow/bin/merge-task.sh")
    text = payload_text("claude/skills/pad-run/SKILL.md")
    assert "merge-task.sh --run" in text
    assert "Write none of those again" in " ".join(text.split())
