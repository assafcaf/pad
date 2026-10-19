"""PAD 0.4.0: /pad-run governs the run from files (redesign brief, sections 2.4 and 2.5).

Content tests: the skill's prose is the product, so these read it. Prose wraps anywhere, so
most checks read the text with its whitespace collapsed.
"""
from __future__ import annotations

import re

import pytest

SKILL = "claude/skills/pad-run/SKILL.md"
ALIAS = "claude/skills/batch-implement/SKILL.md"
TEMPLATE = "claude/workflow/brief-template.md"


def flat(text: str) -> str:
    return " ".join(text.split())


def section(text: str, heading: str) -> str:
    """Body of the `## <heading>` section, up to the next `## ` heading."""
    m = re.search(r"^## " + re.escape(heading) + r"[ \t]*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert m, f"no '## {heading}' section"
    return m.group(1)


def step(text: str, letter: str, title: str) -> str:
    """Body of a bold `**<letter>. <title>.**` step in section 3, up to the next step."""
    m = re.search(r"^\*\*%s\. %s[.,]\*\*(.*?)(?=^\*\*[a-z]\. |^## )" % (letter, re.escape(title)),
                  text, re.M | re.S)
    assert m, f"no step {letter}. {title}"
    return flat(m.group(1))


def sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+(?=[A-Z`*])", flat(text))


def report_row(text: str, start: str) -> str:
    rows = [l for l in text.splitlines() if l.lstrip().startswith(f"| {start}")]
    assert len(rows) == 1, f"reports table has no single row starting {start!r}"
    return rows[0]


# The orchestrator's role


def test_orchestrator_never_writes_product_code_and_never_relays(payload_text):
    text = flat(payload_text(SKILL))
    assert "Your verbs are partition, sequence, land, replan and escalate." in text
    assert "You never write product code" in text
    assert "never carry a message between two agents" in text


def test_skill_names_owner_and_evaluator_and_no_retired_agent(payload_text):
    text = payload_text(SKILL)
    for agent in ("owner", "test-designer", "evaluator", "tracker", "memory-curator"):
        assert re.search(r"^\| `%s` \|" % agent, text, re.M), agent
    for retired in ("ticket-owner", "code-writer", "epic-merger", "task-planner"):
        assert retired not in text, retired


# Dispatch carries only the ticket and the brief


def test_dispatch_carries_only_the_paths_and_records_the_owner_by_script(payload_text):
    body = step(payload_text(SKILL), "b", "Dispatch one `owner` per ticket, in one message")
    assert "Each prompt carries only the ticket file's absolute path and the brief's" in body
    assert "Name each `<task key>-owner`" in body
    assert "`<KEY>-owner <agent id>` into its row of the brief's ownership map" in body
    assert "dispatch <KEY> <KEY>-owner <agent id>" in body
    assert "ledger.sh <KEY> status doing" in body
    assert '--run <run id> --owner "<KEY>-owner <agent id>"' in body


def test_ticket_bodies_are_files_never_text(payload_text):
    text = flat(payload_text(SKILL))
    assert "Write each ticket body once," in text
    assert "`.work/runs/<run id>/tickets/<KEY>.md`" in text
    assert "never the body as text" in text


def test_owner_reads_only_the_two_paths_it_is_given(payload_text):
    owner = flat(payload_text("claude/agents/owner.md"))
    assert "Your dispatch carries two paths: the ticket and the run's brief" in owner


# The brief


def test_brief_is_written_from_the_template(payload_text):
    start = flat(section(payload_text(SKILL), "2. Start"))
    assert "**Write the brief.** Fill `.claude/workflow/brief-template.md` into" in start
    assert "`.work/runs/<run id>/brief.md` with `Write`" in start
    assert "Link, never paraphrase" in start
    assert payload_text(TEMPLATE)


def test_rulings_are_appended_to_the_brief(payload_text):
    text = payload_text(SKILL)
    appends = [s for s in sentences(text) if "## Rulings" in s and re.search(r"append", s, re.I)]
    assert len(appends) >= 3, appends
    row = report_row(text, "Owner `NEEDS_RULING")
    assert "append the answer to the brief's `## Rulings`" in row


def test_run_files_live_in_the_main_checkout(payload_text):
    text = payload_text(SKILL)
    assert "`.work/runs/<run id>/` in the" in text
    for name in ("scope.md", "brief.md", "board.md", "channel.md", "progress.md"):
        assert re.search(r"^\| `%s` \|" % re.escape(name), text, re.M), name
    board = [l for l in text.splitlines() if l.startswith("| `board.md`")][0]
    assert "Scripts only (`ledger.sh --run`)" in board
    channel = [l for l in text.splitlines() if l.startswith("| `channel.md`")][0]
    assert "`channel.sh post`" in channel


# Landing a READY


def test_ready_runs_one_background_merge_task_with_protected_ticket_and_run(payload_text):
    row = report_row(payload_text(SKILL), "Owner `READY")
    assert row.count("merge-task.sh") == 1, row
    assert "bash .claude/workflow/bin/merge-task.sh" in row
    assert "in the background (`run_in_background`), and end your turn" in row
    assert "That is the whole hand-off: one turn" in row
    assert "--protected \"<the config's Protected paths>\"" in row
    assert "--ticket <ticket file>" in row
    assert "--run <run id>" in row
    assert "--typecheck" in row


def test_a_visual_ticket_merge_adds_capture_with_render_check(payload_text):
    row = report_row(payload_text(SKILL), "Owner `READY")
    m = re.search(r"--capture \"([^\"]*)\"", row)
    assert m, row
    assert "bash .claude/workflow/bin/render-check.sh" in m.group(1)
    assert "{out}" in m.group(1)
    assert re.search(r"reference is a mock crop on a surface with a Render command", row)


def test_orchestrator_never_reads_diffs_or_merge_output(payload_text):
    body = step(payload_text(SKILL), "c", "Act on the reports")
    assert "Never read diffs, logs or merge output into your context" in body


def test_merged_needs_no_write_because_the_script_recorded_it(payload_text):
    row = report_row(payload_text(SKILL), "`merge-task.sh` `MERGED")
    assert "Nothing to write: the script recorded it" in row


# Review, channel and replan


# Step 3f (Review every wave) is covered in test_review_content.py.


def test_replan_writes_new_tickets_through_tickets_lint(payload_text):
    body = step(payload_text(SKILL), "g", "Replan")
    assert "**new tickets**" in body
    assert "`/tickets`' sections 1 and 2" in body
    assert "its lint, `plan-check.sh`, included" in body
    assert "shown to the operator before they are published" in body
    assert "A merged ticket is never reopened" in body


def test_stall_rule_replans_a_twice_failed_ticket(payload_text):
    row = report_row(payload_text(SKILL), "Owner `FAILED")
    assert "**Stall rule:** a ticket that fails twice is replanned (3g)" in row
    assert "never re-dispatched as it is" in row
    assert "a split of a twice-failed ticket" in step(payload_text(SKILL), "g", "Replan")


def test_start_runs_plan_check_and_sends_planning_errors_back(payload_text):
    start = flat(section(payload_text(SKILL), "2. Start"))
    assert "bash .claude/workflow/bin/plan-check.sh .work/runs/<run id>/tickets" in start
    assert "planning errors: send them back to `/tickets`" in start


# Resume


def test_resume_reads_the_run_files_and_git_log(payload_text):
    text = flat(payload_text(SKILL))
    m = re.search(r"\*\*Resuming in a new session\.\*\*(.*?)\*\*After compaction", text)
    assert m, "no resume paragraph"
    body = m.group(1)
    assert "`git log` on the epic branch" in body
    assert "`Merge <KEY>` commit is on the epic branch is merged" in body
    assert "starts over with a new owner" in body
    assert "the ticket, the brief, the channel" in body
    assert "Ownership belongs to the ticket, not the agent" in body


def test_after_compaction_restarts_nothing_and_trusts_the_files(payload_text):
    text = flat(payload_text(SKILL))
    assert "restart nothing" in text
    assert "trust the run files and `git log` over your memory" in text


# Finish and clean up


def test_finish_measures_the_run_with_run_stats_and_opens_a_draft_pr(payload_text):
    finish = flat(section(payload_text(SKILL), "4. Finish the epic"))
    assert "`bash .claude/workflow/bin/run-stats.sh --run <run id>`" in finish
    assert "the run's `STAT` lines" in finish
    assert "`gh pr create --draft`" in finish


def test_cleanup_runs_after_the_operator_merges_the_pr(payload_text):
    body = flat(section(payload_text(SKILL), "5. After the PR merges: clean up"))
    assert "The operator merges the PR, never you." in body
    assert "`bash .claude/workflow/bin/cleanup-run.sh --run <run id> --epic-branch <epic branch>`" in body
    assert "run from the main checkout" in body
    assert "It refuses unless the epic is merged" in body
    assert "never removes a worktree with uncommitted changes" in body
    assert "gh pr merge" not in payload_text(SKILL)


# Never block the session, never move it


@pytest.mark.parametrize("tool", ["AskUserQuestion", "EnterWorktree"])
def test_never_calls_a_session_blocking_or_moving_tool(payload_text, tool):
    hits = [s for s in sentences(payload_text(SKILL)) if tool in s]
    assert hits, f"skill no longer forbids {tool}"
    assert all(re.search(r"\bNever\b", s) for s in hits), hits
    if tool == "EnterWorktree":
        assert "git -C .claude/worktrees/<KEY>" in payload_text(SKILL)


# The old name


def test_batch_implement_is_an_alias_for_pad_run(payload_text):
    text = payload_text(ALIAS)
    front, body = text.split("---", 2)[1:]
    assert re.search(r"^name: batch-implement$", front, re.M)
    assert re.search(r"^disable-model-invocation: true$", front, re.M)
    assert "/pad-run" in front
    assert "`.claude/skills/pad-run/SKILL.md`" in body
    assert "$ARGUMENTS" in body
    paragraphs = [p for p in re.split(r"\n\s*\n", body) if p.strip()]
    assert len(paragraphs) == 1, paragraphs


def test_pad_run_skill_is_named_pad_run(payload_text):
    front = payload_text(SKILL).split("---", 2)[1]
    assert re.search(r"^name: pad-run$", front, re.M)
    assert re.search(r"^disable-model-invocation: true$", front, re.M)
