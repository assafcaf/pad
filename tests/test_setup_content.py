"""E1-T26: /setup-workflow runs one named step on its own (O41) and probes capabilities (O42).

Content tests: the skill's prose is the product. A sub-run is an argument to /setup-workflow
(`moves`, `surfaces`, `load`, `capabilities`, `rehearse`, `upgrade`) that redoes only its own
step. The skill says so in a line per sub-run that names that step's `## ` section, by title or
as `step <n>`; the section it names is the one that holds the step's own work.

O42 is `live` (serial): its probe is the ticket's "Live probe (O42)" — run
`/setup-workflow capabilities` with Remote Control connected. The tests below check the step's
instructions only.
"""
from __future__ import annotations

import re

import pytest

from test_preflight import OLD_VERSION, config_md, install, preflight  # noqa: F401

SKILL = "claude/skills/setup-workflow/SKILL.md"

SUB_RUNS = ["moves", "surfaces", "load", "capabilities", "rehearse", "upgrade"]

# What only the right step's section holds: a sub-run mapped to any other section fails.
MARKERS = {
    "moves": "check-moves.sh",
    "surfaces": "knowledge-scanner",
    "load": "load-probe.sh",
    "capabilities": "push notification",
    "rehearse": "rehearse.sh",
    "upgrade": "PAD version",
}


def frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert m, "no frontmatter"
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def sections(text: str) -> list[tuple[str, str, str]]:
    """(number, title, body) for each `## `/`### ` heading; number is '' when unnumbered."""
    heads = list(re.finditer(r"^#{2,3} (.+)$", text, re.M))
    out = []
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        m = re.match(r"(\w+)\.\s+(.+)", h.group(1).strip())
        number, title = (m.group(1), m.group(2)) if m else ("", h.group(1).strip())
        out.append((number, title.strip(), text[h.end():end]))
    return out


def named_sections(line: str, secs) -> list[tuple[str, str, str]]:
    """The sections a line names: by its title, or as `step <n>` / `§<n>`."""
    hits = []
    for number, title, body in secs:
        by_title = title.lower() in line.lower()
        by_number = bool(number) and re.search(
            rf"(?:\bsteps?\s*|§\s*){re.escape(number)}\b", line, re.I
        )
        if by_title or by_number:
            hits.append((number, title, body))
    return hits


def sub_run_lines(text: str, name: str) -> list[str]:
    body = text.split("\n---\n", 1)[1] if text.startswith("---") else text
    pat = re.compile(rf"`(?:/setup-workflow\s+)?{re.escape(name)}`")
    return [line for line in body.splitlines() if pat.search(line)]


def step_for(text: str, name: str) -> list[tuple[str, str, str]]:
    """The sections some line for this sub-run names, all of which hold its marker."""
    secs = sections(text)
    for line in sub_run_lines(text, name):
        hits = named_sections(line, secs)
        if hits and all(MARKERS[name] in body for _, _, body in hits):
            return hits
    return []


def paragraphs(text: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def capabilities_step(text: str) -> str:
    hits = step_for(text, "capabilities")
    assert hits, "no line maps the `capabilities` sub-run to a step holding its probe"
    return "\n".join(body for _, _, body in hits)


def local_md_template(text: str) -> str:
    m = re.search(r"```markdown\n(# Local environment.*?)```", text, re.S)
    assert m, "no CLAUDE.local.md template"
    return m.group(1)


# --- O41: named sub-runs ------------------------------------------------------------------------


def test_o41_argument_hint_offers_every_sub_run_beside_the_trackers(payload_text):
    hint = frontmatter(payload_text(SKILL))["argument-hint"]
    for name in SUB_RUNS + ["jira", "github", "local"]:
        assert re.search(rf"\b{name}\b", hint), f"{name!r} missing from argument-hint {hint!r}"


def test_o41_the_input_paragraph_accepts_a_sub_run_as_the_argument(payload_text):
    paras = [p for p in paragraphs(payload_text(SKILL)) if "$ARGUMENTS" in p]
    assert paras, "no paragraph reads $ARGUMENTS"
    assert any(re.search(r"sub-runs?", p, re.I) for p in paras), paras


@pytest.mark.parametrize("name", SUB_RUNS)
def test_o41_each_sub_run_names_the_one_step_that_does_its_work(payload_text, name):
    text = payload_text(SKILL)
    lines = sub_run_lines(text, name)
    assert lines, f"no line names the `{name}` sub-run"
    assert step_for(text, name), (
        f"no line for `{name}` names only sections holding {MARKERS[name]!r}: {lines}"
    )


def test_o41_sub_runs_map_to_six_different_steps(payload_text):
    text = payload_text(SKILL)
    titles = {}
    for name in SUB_RUNS:
        hits = step_for(text, name)
        assert hits, f"`{name}` maps to no step"
        titles[name] = frozenset(title for _, title, _ in hits)
    assert len(set(titles.values())) == len(SUB_RUNS), titles


def test_o41_a_sub_run_redoes_only_its_own_step(payload_text):
    paras = [p for p in paragraphs(payload_text(SKILL)) if re.search(r"sub-runs?", p, re.I)]
    assert any(
        re.search(r"\bonly\b", p, re.I) and re.search(r"\b(skip|skips|skipping|no other|none of the other|not the others?)\b", p, re.I)
        for p in paras
    ), paras


def test_o41_with_no_sub_run_setup_runs_every_step(payload_text):
    paras = [p for p in paragraphs(payload_text(SKILL)) if re.search(r"sub-runs?", p, re.I)]
    assert any(
        re.search(r"\b(no|without( a)?)\s+sub-run", p, re.I)
        and re.search(r"\b(every|all)\b[^.]*\bsteps?\b", p, re.I)
        for p in paras
    ), paras


def test_o41_an_unknown_argument_is_refused_naming_the_sub_runs(payload_text):
    paras = [p for p in paragraphs(payload_text(SKILL)) if re.search(r"sub-runs?", p, re.I)]
    assert any(
        re.search(r"\b(unknown|unrecogni[sz]ed|any other|not one of|anything else)\b", p, re.I)
        and re.search(r"\b(stop|refuse|ask)", p, re.I)
        for p in paras
    ), paras


def test_o41_a_sub_run_skips_asking_for_the_tracker(payload_text):
    paras = [
        p for p in paragraphs(payload_text(SKILL))
        if re.search(r"sub-runs?", p, re.I) and re.search(r"tracker", p, re.I)
    ]
    assert any(re.search(r"\b(not|never|no need|without)\b", p, re.I) for p in paras), paras


@pytest.mark.parametrize("version", [OLD_VERSION, None])
def test_o41_every_sub_run_preflight_names_is_one_setup_accepts(
    repo, preflight, payload_text, version  # noqa: F811
):
    install(repo, config=config_md(version=version, omit=("Surfaces",)))
    result = preflight(repo)
    named = set(re.findall(r"/setup-workflow (\w+)", result.stdout + result.stderr))
    assert named, result.stdout
    text = payload_text(SKILL)
    hint = frontmatter(text)["argument-hint"]
    for name in named:
        assert re.search(rf"\b{name}\b", hint), f"preflight names {name!r}; hint is {hint!r}"
        assert name in MARKERS and step_for(text, name), f"no step for preflight's {name!r}"


def test_o41_upgrade_step_adds_the_sections_preflight_names_as_missing(payload_text):
    text = payload_text(SKILL)
    hits = step_for(text, "upgrade")
    assert hits, "`upgrade` maps to no step"
    body = "\n".join(b for _, _, b in hits)
    assert "preflight" in body, body
    assert re.search(r"missing|lacks|sections? to add|add[^.]*sections?", body, re.I), body


def test_o41_upgrade_step_records_the_installed_pad_version(payload_text):
    text = payload_text(SKILL)
    body = "\n".join(b for _, _, b in step_for(text, "upgrade"))
    assert re.search(r"PAD version[^.]*(install|VERSION)|(install|VERSION)[^.]*PAD version", body), body


def test_o41_upgrade_step_keeps_the_values_already_in_the_config(payload_text):
    text = payload_text(SKILL)
    body = "\n".join(b for _, _, b in step_for(text, "upgrade"))
    assert re.search(r"\b(keep|keeping|preserv|leave|leaving|without (changing|overwriting))", body, re.I), body


# --- O42: capabilities --------------------------------------------------------------------------


def test_o42_capabilities_step_checks_whether_the_workflow_tool_is_available(payload_text):
    step = capabilities_step(payload_text(SKILL))
    assert "Workflow tool" in step, step
    assert re.search(r"availab", step, re.I), step


def test_capabilities_step_sets_no_execution_mode(payload_text):
    """0.4.0: one pipeline, so the Workflow tool's presence is recorded, not configured."""
    step = capabilities_step(payload_text(SKILL))
    assert "set it to `owner`" not in step, step
    assert "`workflow` in `config.md`" not in step, step
    assert re.search(r"no execution mode", step, re.I), step


def test_o42_capabilities_step_sends_a_test_push_notification(payload_text):
    step = capabilities_step(payload_text(SKILL))
    assert re.search(r"test push notification|push notification[^.]*\btest\b", step, re.I), step


def test_o42_capabilities_step_asks_the_operator_to_confirm_receiving_the_push(payload_text):
    step = capabilities_step(payload_text(SKILL))
    assert re.search(r"confirm", step, re.I), step
    assert re.search(r"\b(ask|asks|asking)\b", step, re.I), step


def test_o42_capabilities_step_records_both_results_in_claude_local_md(payload_text):
    step = capabilities_step(payload_text(SKILL))
    assert "CLAUDE.local.md" in step, step


def test_o42_capabilities_step_records_an_unconfirmed_push_as_not_received(payload_text):
    step = capabilities_step(payload_text(SKILL))
    assert re.search(
        r"(not|never|didn't|did not)[^.]*(receiv|arriv|confirm)|unconfirmed", step, re.I
    ), step


def test_o42_local_md_template_has_a_workflow_tool_line(payload_text):
    template = local_md_template(payload_text(SKILL))
    assert re.search(r"^- Workflow tool:", template, re.M), template


def test_o42_local_md_template_has_a_push_notification_line(payload_text):
    template = local_md_template(payload_text(SKILL))
    assert re.search(r"^- Push notifications?:", template, re.M), template
    assert re.search(r"confirm", template, re.I), template


# --- 0.4.0: agents, config sections, allow rules, rehearsal steps -------------------------------

AGENTS_040 = ["owner", "test-designer", "evaluator", "tracker", "knowledge-scanner",
              "memory-curator"]


def _harness_step(text: str) -> str:
    return next(body for number, title, body in sections(text) if title == "The harness")


def test_harness_step_lists_the_current_agents(payload_text):
    body = _harness_step(payload_text(SKILL))
    rows = re.findall(r"^\s*\| `([a-z-]+)` \|", body, re.M)
    assert rows == AGENTS_040, rows


def test_harness_step_names_retired_agents_only_to_delete_them(payload_text):
    body = _harness_step(payload_text(SKILL))
    para = next(p for p in paragraphs(body) if "ticket-owner" in p)
    assert "delete" in para and "code-writer" in para and "task-planner" in para


def test_harness_allow_rules_match_settings_example(payload_text):
    import json
    body = _harness_step(payload_text(SKILL))
    flat = " ".join(body.split())
    assert "Bash(git rebase *)" in flat
    allow = json.loads(payload_text("claude/settings.example.json"))["permissions"]["allow"]
    scripts = [m.group(1) for r in allow
               for m in [re.match(r"Bash\(bash \.claude/workflow/bin/([a-z-]+)\.sh \*\)", r)] if m]
    assert scripts, allow
    for script in scripts:
        assert f"`{script}`" in flat, script


def test_config_step_names_protected_paths_and_cadence_and_drops_tiers_and_mode(payload_text):
    text = payload_text(SKILL)
    body = next(b for n, t, b in sections(text) if t == "Protected paths and review")
    assert "## Protected paths" in body
    assert "`per-wave`" in body
    assert re.search(r"no tiers and no execution mode", body, re.I)


def test_surfaces_step_names_the_three_visual_columns(payload_text):
    text = payload_text(SKILL)
    body = "\n".join(b for _, _, b in step_for(text, "surfaces"))
    for column in ("Reference dir", "Render command", "Viewport"):
        assert f"**{column}**" in body, column
    assert "render-check.sh" in body
    assert re.search(r"no visual class", body)


def test_upgrade_step_names_the_040_config_changes(payload_text):
    body = "\n".join(b for _, _, b in step_for(payload_text(SKILL), "upgrade"))
    for part in ("## Protected paths", "Render command", "Viewport", "Reference dir",
                 "rebase-onto-epic-head", "### Tiers", "Mode"):
        assert part in body, part


def test_rehearsal_step_lists_every_rehearse_step(payload_text):
    from test_rehearse import STEPS
    body = "\n".join(b for _, _, b in step_for(payload_text(SKILL), "rehearse"))
    for step in STEPS:
        assert f"`{step}`" in body, step


def test_setup_has_no_tier_or_mode_instructions_left(payload_text):
    text = payload_text(SKILL)
    assert "Execution → Mode" not in text
    assert "/batch-implement" not in text
