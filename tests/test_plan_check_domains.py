"""plan-check.sh binds the ticket split to the spec's domains (O45, O46, O48)."""
from __future__ import annotations

from pathlib import Path

SPEC = (
    "# Spec\n\n## Domains\n"
    "- **host**: the memory cap. Owns `pad-proc*`.\n"
    "- planning: domains bind the split. Owns `plan-check.sh`.\n\n"
    "## Outcomes\n- [O1] x\n"
)


def body(owns, domain=None, split=None) -> str:
    s = "## Outcome\nSomething is true.\n\n## Reference\nO1\n"
    if domain is not None:
        s += f"\n## Domain\n{domain}\n"
    s += "\n## Owns\n" + "".join(f"- {p}\n" for p in owns)
    s += "\n## Touches\nnone\n\n## Protected\nno\n\n## Depends on\nnone\n"
    if split is not None:
        s += f"\n## Split\n{split}\n"
    return s + "\n## Out of scope\nNothing.\n"


def plan(root: Path, tickets: dict[str, str], spec: str | None = SPEC) -> Path:
    head = "# Plan: thing\n\n"
    if spec is not None:
        sp = root / "spec.md"
        sp.write_text(spec, encoding="utf-8")
        head += f"Spec: {sp.as_posix()}\n\n"
    text = head
    for key, t in tickets.items():
        text += f"### {key} — a title\n\n{t}\n"
    p = root / "plan.md"
    p.write_text(text, encoding="utf-8")
    return p


def check(run_script, repo, p):
    r = run_script("plan-check.sh", str(p), cwd=repo)
    return r, r.stdout.strip().splitlines()


def test_one_ticket_per_domain_passes_with_no_domain_findings(repo, run_script):
    p = plan(repo, {"E1-T1": body(["a/x"], "host"), "E1-T2": body(["b/y"], "planning")})
    r, out = check(run_script, repo, p)
    assert r.returncode == 0, r.stdout + r.stderr
    assert out[-1] == "PLAN OK"
    assert not [l for l in out if l.startswith(("DOMAIN", "SPLIT"))]


def test_ticket_naming_a_domain_the_spec_lacks_fails(repo, run_script):
    p = plan(repo, {"E1-T1": body(["a/x"], "host"), "E1-T2": body(["b/y"], "planning"),
                    "E1-T3": body(["c/z"], "bogus")})
    r, out = check(run_script, repo, p)
    assert r.returncode == 1
    assert "DOMAIN E1-T3: unknown bogus" in out
    assert out[-1].startswith("PLAN FAIL")


def test_ticket_with_no_domain_section_fails(repo, run_script):
    p = plan(repo, {"E1-T1": body(["a/x"], "host"), "E1-T2": body(["b/y"], "planning"),
                    "E1-T3": body(["c/z"])})
    r, out = check(run_script, repo, p)
    assert r.returncode == 1
    assert any(l.startswith("DOMAIN E1-T3: unknown") for l in out), out
    assert out[-1].startswith("PLAN FAIL")


def test_spec_domain_no_ticket_names_fails(repo, run_script):
    p = plan(repo, {"E1-T1": body(["a/x"], "host")})
    r, out = check(run_script, repo, p)
    assert r.returncode == 1
    assert "DOMAIN planning: no ticket" in out
    assert "DOMAIN host: no ticket" not in out
    assert out[-1].startswith("PLAN FAIL")


def test_two_tickets_in_a_domain_without_split_fail(repo, run_script):
    p = plan(repo, {"E1-T1": body(["a/x"], "host"), "E1-T2": body(["a/y"], "host"),
                    "E1-T3": body(["b/y"], "planning")})
    r, out = check(run_script, repo, p)
    assert r.returncode == 1
    assert "SPLIT host: 2 tickets" in out
    assert out[-1].startswith("PLAN FAIL")


def test_split_missing_on_one_ticket_of_the_domain_fails(repo, run_script):
    p = plan(repo, {"E1-T1": body(["a/x"], "host", "independent-surface"),
                    "E1-T2": body(["a/y"], "host"), "E1-T3": body(["b/y"], "planning")})
    r, out = check(run_script, repo, p)
    assert r.returncode == 1
    assert "SPLIT host: 2 tickets" in out


def test_split_with_unlisted_reason_fails(repo, run_script):
    p = plan(repo, {"E1-T1": body(["a/x"], "host", "too big"), "E1-T2": body(["a/y"], "host", "too big"),
                    "E1-T3": body(["b/y"], "planning")})
    r, out = check(run_script, repo, p)
    assert r.returncode == 1
    assert "SPLIT host: 2 tickets" in out


def test_valid_split_prints_a_line_for_the_approval_table(repo, run_script):
    for reason in ("independent-surface", "parallel-by-interface", "split-after-failures"):
        p = plan(repo, {"E1-T1": body(["a/x"], "host", reason), "E1-T2": body(["a/y"], "host", reason),
                        "E1-T3": body(["b/y"], "planning")})
        r, out = check(run_script, repo, p)
        assert r.returncode == 0, r.stdout + r.stderr
        assert f"SPLIT host: E1-T1 E1-T2 ({reason})" in out
        assert out[-1] == "PLAN OK"


def test_operator_split_needs_the_operators_words_quoted(repo, run_script):
    bare = plan(repo, {"E1-T1": body(["a/x"], "host", "operator"), "E1-T2": body(["a/y"], "host", "operator"),
                       "E1-T3": body(["b/y"], "planning")})
    r, out = check(run_script, repo, bare)
    assert r.returncode == 1
    assert "SPLIT host: 2 tickets" in out
    q = 'operator "split it, I want two reviewers"'
    ok = plan(repo, {"E1-T1": body(["a/x"], "host", q), "E1-T2": body(["a/y"], "host", q),
                     "E1-T3": body(["b/y"], "planning")})
    r, out = check(run_script, repo, ok)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SPLIT host: E1-T1 E1-T2 (operator)" in out


def test_plan_without_a_spec_line_skips_the_domain_checks(repo, run_script):
    p = plan(repo, {"E1-T1": body(["a/x"]), "E1-T2": body(["b/y"], "whatever")}, spec=None)
    r, out = check(run_script, repo, p)
    assert r.returncode == 0, r.stdout + r.stderr
    assert len([l for l in out if l.startswith("DOMAIN skipped:")]) == 1
    assert not [l for l in out if l.startswith("SPLIT")]
    assert out[-1] == "PLAN OK"


def test_spec_without_domains_skips_the_domain_checks(repo, run_script):
    p = plan(repo, {"E1-T1": body(["a/x"]), "E1-T2": body(["b/y"])}, spec="# Spec\n\n## Outcomes\n- x\n")
    r, out = check(run_script, repo, p)
    assert r.returncode == 0, r.stdout + r.stderr
    assert len([l for l in out if l.startswith("DOMAIN skipped:")]) == 1
    assert out[-1] == "PLAN OK"


def test_skipped_domain_checks_leave_other_checks_unchanged(repo, run_script):
    p = plan(repo, {"E1-T1": body(["a/x"]), "E1-T2": body(["a/x"])}, spec=None)
    r, out = check(run_script, repo, p)
    assert r.returncode == 1
    assert "OVERLAPS E1-T1 E1-T2: a/x" in out
    assert len([l for l in out if l.startswith("DOMAIN skipped:")]) == 1
    assert out[-1] == "PLAN FAIL 1"


def test_list_output_is_unchanged_by_domain_and_split_sections(repo, run_script):
    f = repo / "E1-T1.md"
    f.write_text(body(["a/x"], "host", "independent-surface"), encoding="utf-8")
    r = run_script("plan-check.sh", "--list", str(f), cwd=repo)
    assert r.returncode == 0
    assert r.stdout.strip().splitlines() == ["OWNS a/x"]
