"""PAD 0.4.0: the run's brief and channel are how a team of owners shares intent.

Content tests for `workflow/brief-template.md`, the `read-channel-first` rule and the owner's
channel steps: the prose is the product.
"""
from __future__ import annotations

import re

TEMPLATE = "claude/workflow/brief-template.md"
RULE = "claude/workflow/rules/read-channel-first.md"
OWNER = "claude/agents/owner.md"


def flat(text: str) -> str:
    return " ".join(text.split())


def template_block(payload_text) -> str:
    m = re.search(r"```markdown\n(.*?)```", payload_text(TEMPLATE), re.S)
    assert m, "brief template has no markdown block"
    return m.group(1)


# The brief template


def test_brief_template_has_every_section_in_order(payload_text):
    headings = re.findall(r"^## (.+)$", template_block(payload_text), re.M)
    assert headings == [
        "Sources of truth", "The system already in the code", "Rules in force", "Gates",
        "Ownership map and team", "Protocol", "Rulings",
    ]


def test_brief_template_keeps_the_brief_under_about_sixty_lines(payload_text):
    assert "under about 60 lines" in flat(payload_text(TEMPLATE))
    lines = template_block(payload_text).splitlines()
    assert len(lines) <= 60, len(lines)


def test_brief_template_links_and_never_paraphrases(payload_text):
    text = flat(payload_text(TEMPLATE))
    assert "**links** to the sources of truth and never paraphrases them" in text
    assert "Don't copy bodies." in text


def test_brief_links_the_scope_and_definition_of_done(payload_text):
    block = template_block(payload_text)
    assert "`.work/runs/<epic>/scope.md`" in block
    assert "`.claude/workflow/definition-of-done.md`" in block
    assert "`docs/decisions/" in block


def test_brief_ownership_map_has_owns_touches_protected_and_owner(payload_text):
    block = template_block(payload_text)
    assert "| Ticket | Owns | Touches | Protected | Owner |" in block


def test_brief_protocol_is_one_report_line(payload_text):
    block = flat(template_block(payload_text))
    for line in ("`READY <KEY> <head> <red>`", "`FAILED <KEY> <why>`",
                 "`NEEDS_RULING <KEY> <question>`"):
        assert line in block, line
    assert "A write outside your Owns ∪ Touches is a request" in block
    assert "A ticket that fails twice is replanned." in block


def test_brief_gates_never_run_the_full_suite(payload_text):
    assert "Never the full suite" in template_block(payload_text)


def test_brief_rulings_are_appended_by_the_orchestrator(payload_text):
    block = template_block(payload_text)
    rulings = block[block.index("## Rulings"):]
    assert "Appended by the orchestrator" in rulings


def test_brief_names_the_channel_commands(payload_text):
    block = flat(template_block(payload_text))
    assert "bash .claude/workflow/bin/channel.sh post <epic> <KEY> \"<line>\"" in block
    assert "channel.sh read <epic>" in block


# The read-channel-first rule


def test_read_channel_first_rule_applies_to_owner_and_test_designer(payload_text):
    front = payload_text(RULE).split("---")[1]
    assert re.search(r"^name: read-channel-first$", front, re.M)
    assert re.search(r"^kind: practice$", front, re.M)
    assert re.search(r"^applies-to: owner, test-designer$", front, re.M)


def test_read_channel_first_rule_reads_before_writing_and_before_every_rebase(payload_text):
    body = flat(payload_text(RULE).split("---", 2)[2])
    assert "before you write anything and again before every rebase" in body
    assert "`bash .claude/workflow/bin/channel.sh read <run id>`" in body
    assert "`channel.sh post <run id> <KEY> \"<line>\"`" in body


# The owner's channel steps


def test_owner_reads_the_channel_on_start(payload_text):
    text = flat(payload_text(OWNER))
    m = re.search(r"## What you read(.*?)## The strict discipline", text)
    assert m
    assert "the channel (`bash .claude/workflow/bin/channel.sh read <run id>`)" in m.group(1)


def test_owner_reads_the_channel_again_before_rebasing(payload_text):
    text = flat(payload_text(OWNER))
    m = re.search(r"7\. \*\*Rebase onto the epic head\.\*\*(.*?)8\. \*\*Report", text)
    assert m
    assert "Read the channel again first (`channel.sh read <run id> --since <your start>`)" in m.group(1)


def test_owner_posts_shared_changes_to_the_channel(payload_text):
    text = flat(payload_text(OWNER))
    assert "**Post to the channel** whenever you change a shared file (`Touches`)" in text
    assert "`bash .claude/workflow/bin/channel.sh post <run id> <KEY> \"<one line>\"`" in text


def test_owner_talks_to_peers_directly_never_through_the_orchestrator(payload_text):
    text = flat(payload_text(OWNER))
    assert "never route a peer question through the orchestrator" in text
