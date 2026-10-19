"""O3: merge-ticket.sh lands one ticket, reading every merge-task.sh argument from the config,
the run and the ticket file.

    merge-ticket.sh [--print-args] --run <id> [--expect-tree <tree>] <KEY> <TASK_HEAD> <RED>

Run from the main checkout. The epic worktree is `<main>/.claude/worktrees/<id>` (its checked-out
branch is the epic branch), the ticket is `<main>/.work/runs/<id>/tickets/<KEY>.md` and the config
is `<main>/.claude/workflow/config.md`. `--print-args` prints the resolved merge-task.sh
arguments, one per line, and runs nothing.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from conftest import git
from test_merge_task import _commit, _task

KEY = "E1-T1"
RUN = "R1"
TITLE = "Add the impl — with a dash"
GATE = 'grep -q "X = 1" src/impl.py'
WRONG_TREE = "0" * 40

CONFIG = f"""# Workflow config

PAD version: 0.4.0

## Protected paths

- `src/secret/**`
- `db/*.sql`

## Execution

- **Gate:** `full`.
- **Test workers:** `none`.

## Commands

| Gate | Command |
|---|---|
| Setup in a fresh worktree | `true` (nothing to install) |
| Run named tests | `{GATE}` (the named tests) |
| Full suite | `{GATE}` |
| Typecheck | `true` (none configured) |
| Lint | `echo lint-ran` (lint) |
| Test paths | `tests/` |
| Derived files | none |
"""

TICKET = f"""---
key: {KEY}
title: "{TITLE}"
status: doing
---

## Outcome
Something.

## Outcomes
- [O1] first, written with a dash bullet.
* [O2] second, written with a star bullet.

## Owns
- `src/impl.py`
- `tests/test_new.py`

## Touches
none

## Protected
{{protected}}

## Spec
- [O9] not an outcome of this ticket: it sits outside the Outcomes section.
"""


def _setup(repo: Path, worktree, *, protected: str = "no", ticket: bool = True):
    """Main checkout with config + ticket, epic worktree <main>/.claude/worktrees/R1 on `epic`."""
    exclude = repo / ".git" / "info" / "exclude"
    exclude.parent.mkdir(exist_ok=True)
    exclude.write_text(".claude/\n.work/\n", encoding="utf-8")
    cfg = repo / ".claude" / "workflow" / "config.md"
    cfg.parent.mkdir(parents=True)
    cfg.write_bytes(CONFIG.encode("utf-8"))
    if ticket:
        t = repo / ".work" / "runs" / RUN / "tickets" / f"{KEY}.md"
        t.parent.mkdir(parents=True)
        t.write_bytes(TICKET.replace("{protected}", protected).encode("utf-8"))
    epic = repo / ".claude" / "worktrees" / RUN
    epic.parent.mkdir(parents=True)
    git("worktree", "add", "-q", "-b", "epic", epic.as_posix(), "main", cwd=repo)
    head = _commit(epic, {"src/base.py": "BASE = 1\n"}, "epic: base")
    git("push", "-q", "-u", "origin", "epic", cwd=epic)
    _, red, task_head = _task(repo, worktree, head)
    return epic, head, red, task_head


def _ticket(run_script, repo, *args: str):
    return run_script("merge-ticket.sh", *args, cwd=repo)


def _last(result) -> str:
    lines = result.stdout.strip().splitlines()
    return lines[-1] if lines else ""


def _after(lines: list[str], opt: str) -> str:
    assert opt in lines, f"{opt} missing from {lines}"
    return lines[lines.index(opt) + 1]


@pytest.mark.slow
def test_o3_landing_a_ticket_with_no_other_arguments_merges_it_and_writes_evidence(
        repo, worktree, run_script):
    epic, epic_head, red, head = _setup(repo, worktree)
    r = _ticket(run_script, repo, "--run", RUN, KEY, head, red)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    sha = git("rev-parse", "HEAD", cwd=epic)
    assert sha != epic_head
    assert _last(r) == f"MERGED {sha}", out
    assert git("log", "-1", "--format=%s", cwd=epic) == f"Merge {KEY}: {TITLE}"
    assert git("log", "-1", "--format=%P", cwd=epic).split() == [epic_head, head]
    assert "BOOKKEEPING FAIL" not in r.stdout
    run_dir = repo / ".work" / "runs" / RUN
    evidence = [p for p in run_dir.rglob("*.md")
                if "tickets" not in p.relative_to(run_dir).parts
                and ("evidence" in p.relative_to(run_dir).parts or p.name == f"{KEY}.md")]
    assert evidence, f"no evidence file under {run_dir}"
    text = "\n".join(p.read_text(encoding="utf-8") for p in evidence)
    assert "O1" in text and "O2" in text, text
    assert "O9" not in text
    assert re.search(rf"\| {KEY} \| O1[ ,]+O2 \|", r.stdout), r.stdout


def test_o3_print_args_lists_the_resolved_arguments_one_per_line_and_runs_nothing(
        repo, worktree, run_script):
    epic, epic_head, red, head = _setup(repo, worktree, protected="yes")
    r = _ticket(run_script, repo, "--print-args", "--run", RUN, KEY, head, red)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert _after(lines, "--run") == RUN
    assert _after(lines, "--gate") == GATE
    assert _after(lines, "--lint") == "echo lint-ran"
    assert _after(lines, "--typecheck") == "true"
    assert _after(lines, "--setup") == "true"
    assert _after(lines, "--test-paths") == "tests/"
    assert _after(lines, "--worktree").replace("\\", "/").endswith(f".claude/worktrees/{RUN}")
    assert _after(lines, "--branch") == "epic"
    assert _after(lines, "--ticket").replace("\\", "/").endswith(
        f".work/runs/{RUN}/tickets/{KEY}.md")
    outcomes = _after(lines, "--outcomes")
    assert "O1" in outcomes and "O2" in outcomes and "O9" not in outcomes
    protected = _after(lines, "--protected")
    assert "src/secret/**" in protected and "db/*.sql" in protected
    assert lines[-4:] == [KEY, red, head, TITLE]
    assert "--expect-tree" not in lines
    assert git("rev-parse", "HEAD", cwd=epic) == epic_head
    assert not (repo / ".work" / "runs" / RUN / f"{KEY}.md").exists()


def test_o3_a_ticket_not_marked_protected_passes_no_protected_globs(repo, worktree, run_script):
    _, _, red, head = _setup(repo, worktree, protected="no")
    r = _ticket(run_script, repo, "--print-args", "--run", RUN, KEY, head, red)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "--protected" not in r.stdout.splitlines()


def test_o3_print_args_passes_expect_tree_through(repo, worktree, run_script):
    _, _, red, head = _setup(repo, worktree)
    r = _ticket(run_script, repo, "--print-args", "--run", RUN, "--expect-tree", WRONG_TREE,
                KEY, head, red)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _after(r.stdout.splitlines(), "--expect-tree") == WRONG_TREE


@pytest.mark.slow
def test_o3_a_wrong_expect_tree_is_rejected_and_the_epic_is_untouched(repo, worktree, run_script):
    epic, epic_head, red, head = _setup(repo, worktree)
    r = _ticket(run_script, repo, "--run", RUN, "--expect-tree", WRONG_TREE, KEY, head, red)
    assert r.returncode == 1, r.stdout + r.stderr
    assert _last(r).startswith(f"REJECTED {KEY}: tree "), r.stdout
    assert git("rev-parse", "HEAD", cwd=epic) == epic_head


def test_o3_a_missing_ticket_file_is_an_error_with_nonzero_exit(repo, worktree, run_script):
    epic, epic_head, red, head = _setup(repo, worktree, ticket=False)
    r = _ticket(run_script, repo, "--run", RUN, KEY, head, red)
    assert r.returncode not in (0, 64)
    assert "ERROR" in r.stdout + r.stderr
    assert git("rev-parse", "HEAD", cwd=epic) == epic_head


def test_o3_an_unknown_run_is_an_error_with_nonzero_exit(repo, worktree, run_script):
    _, _, red, head = _setup(repo, worktree)
    r = _ticket(run_script, repo, "--run", "NOPE", KEY, head, red)
    assert r.returncode not in (0, 64)
    assert "ERROR" in r.stdout + r.stderr
