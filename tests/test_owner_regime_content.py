"""O25, O27, O29: the owner and test-designer prompts under the test regime, and the merge that
makes the owner's unconditional rebase unnecessary.

Content tests for the prompts; one slow unit test pins merge-task.sh's side of O25.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from conftest import git

OWNER = "claude/agents/owner.md"
DESIGNER = "claude/agents/test-designer.md"


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", ""))


def step(text: str, n: int) -> str:
    m = re.search(rf"^{n}\. (.*?)(?=^\d+\. |^\S[^\n]*\n\n(?!\s)|\Z)", text, re.S | re.M)
    assert m, f"no step {n}"
    return flat(m.group(1))


# --- O25 ---


def test_o25_owner_step_7_does_not_rebase_unconditionally(payload_text):
    s7 = step(payload_text(OWNER), 7)
    assert "CONFLICT" in s7
    assert "when it moved" not in s7
    assert "Read the epic head again" not in s7


def test_o25_owner_rebases_only_when_the_merge_reports_conflict(payload_text):
    after = flat(payload_text(OWNER).split("## After READY", 1)[1])
    assert "CONFLICT" in after
    assert "rebase-onto-epic-head" in after


# --- O27 ---


def test_o27_owner_names_new_tests_with_the_ticket_key_in_the_acceptance_pattern(payload_text):
    text = flat(payload_text(OWNER))
    assert "acceptance" in text
    assert "key in the file name" in text or "ticket key in the file name" in text
    assert "acceptance-pattern" in text


def test_o27_test_designer_names_new_tests_with_the_ticket_key_in_the_acceptance_pattern(payload_text):
    text = flat(payload_text(DESIGNER))
    assert "acceptance-pattern" in text
    assert "key in the file name" in text
    assert "prefill.KAN-12.test.ts" in text and "test_store_KAN_12.py" in text


def test_o27_test_designer_runs_tests_only_through_pad_test(payload_text):
    text = flat(payload_text(DESIGNER))
    assert "pad-test.sh" in text
    assert "--role test-designer" in text


# --- O29 ---


def test_o29_test_designer_outcomes_line_states_the_expected_failure_text(payload_text):
    block = payload_text(DESIGNER).split("## Report", 1)[1]
    assert re.search(r"- O1: .*\| expects: ", block)


def test_o29_test_designer_red_must_be_an_assertion_failure_not_an_error(payload_text):
    text = flat(payload_text(DESIGNER))
    assert "--expect-text" in text
    assert "failure" in text and "error" in text


def test_o29_owner_submit_step_names_the_red_grade(payload_text):
    text = flat(payload_text(OWNER))
    assert "red-grade" in text
    assert "tests-in-acceptance" in text


# --- O25: merge-task.sh lands a clean ticket cut from an older epic head, no rebase asked ---

KEY = "T-1"


def _commit(wt: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        p = wt / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        git("add", rel, cwd=wt)
    git("commit", "-q", "-m", msg, cwd=wt)
    return git("rev-parse", "HEAD", cwd=wt)


@pytest.mark.slow
def test_o25_ticket_cut_from_an_older_head_that_merges_cleanly_lands_without_a_rebase(
    repo, worktree, run_script
):
    epic = worktree(repo, "epic")
    old_head = _commit(epic, {"src/base.py": "BASE = 1\n"}, "epic: base")
    git("push", "-q", "-u", "origin", "epic", cwd=epic)
    task = worktree(repo, "task")
    git("reset", "-q", "--hard", old_head, cwd=task)
    red = _commit(task, {"tests/test_new_T_1.py": "def test_new():\n    assert False\n"},
                  f"test({KEY}): O1 [red]")
    head = _commit(task, {"src/impl.py": "X = 1\n"}, f"feat({KEY}): impl")
    _commit(epic, {"src/other.py": "OTHER = 1\n"}, "Merge T-0: another ticket")
    git("push", "-q", "origin", "epic", cwd=epic)
    r = run_script(
        "merge-task.sh", "--worktree", epic.as_posix(), "--branch", "epic",
        "--gate", 'grep -q "X = 1" src/impl.py', "--lint", "true", KEY, red, head, "Add the impl",
        cwd=repo,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1].startswith("MERGED ")
