"""plan-check.sh lints a ticket set: overlaps, hotspots, protected, critical path, sweeps."""
from __future__ import annotations

from pathlib import Path

from conftest import git


def ticket(owns=(), touches=(), protected=None, depends=(), key=None) -> str:
    parts = []
    if key:
        parts.append(f"---\nkey: {key}\n---\n")
    parts.append("## Outcome\nSomething is true.\n\n## Reference\nmock.png\n")
    parts.append("\n## Owns\n" + "".join(f"- {p}\n" for p in owns))
    parts.append("\n## Touches\n" + "".join(f"- {p}\n" for p in touches))
    if protected is not None:
        parts.append(f"\n## Protected\n{protected}\n")
    parts.append("\n## Depends on\n" + ("".join(f"- {d}\n" for d in depends) or "none\n"))
    parts.append("\n## Out of scope\nNothing.\n\n## Spec\n.work/specs/x.md\n")
    return "".join(parts)


def write_dir(root: Path, tickets: dict[str, str]) -> Path:
    d = root / "tickets"
    d.mkdir(parents=True, exist_ok=True)
    for name, body in tickets.items():
        (d / f"{name}.md").write_text(body, encoding="utf-8")
    return d


def write_plan(root: Path, tickets: dict[str, str]) -> Path:
    body = "# Plan: thing\n\n| Wave | Task |\n|---|---|\n| 1 | E1-T1 |\n\n"
    for key, text in tickets.items():
        body += f"### {key} — a title\n\n{text}\n"
    p = root / "plan.md"
    p.write_text(body, encoding="utf-8")
    return p


def lines(r) -> list[str]:
    return r.stdout.strip().splitlines()


def test_disjoint_tickets_pass(repo, run_script):
    d = write_dir(repo, {
        "E1-T1": ticket(owns=["src/a.ts"], protected="no"),
        "E1-T2": ticket(owns=["src/b.ts"], protected="no", depends=["E1-T1"]),
    })
    r = run_script("plan-check.sh", str(d), cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert lines(r)[-1] == "PLAN OK"
    assert "CRITICAL-PATH E1-T1 -> E1-T2" in lines(r)


def test_equal_owns_is_an_overlap(repo, run_script):
    d = write_dir(repo, {
        "E1-T1": ticket(owns=["src/a.ts   (the widget)"]),
        "E1-T2": ticket(owns=["`src/a.ts`"]),
    })
    r = run_script("plan-check.sh", str(d), cwd=repo)
    assert r.returncode == 1
    assert "OVERLAPS E1-T1 E1-T2: src/a.ts" in lines(r)
    assert lines(r)[-1] == "PLAN FAIL 1"


def test_dir_containing_a_file_is_an_overlap(repo, run_script):
    d = write_dir(repo, {
        "E1-T1": ticket(owns=["src/"]),
        "E1-T2": ticket(owns=["src/deep/a.ts"]),
        "E1-T3": ticket(owns=["srcx/b.ts"]),
    })
    r = run_script("plan-check.sh", str(d), cwd=repo)
    assert r.returncode == 1
    over = [l for l in lines(r) if l.startswith("OVERLAPS")]
    assert len(over) == 1
    assert over[0].startswith("OVERLAPS E1-T1 E1-T2: src/deep/a.ts")


def test_frontmatter_key_wins_over_file_name(repo, run_script):
    d = write_dir(repo, {
        "one": ticket(owns=["a.ts"], key="KAN-1"),
        "two": ticket(owns=["a.ts"], key="KAN-2"),
    })
    r = run_script("plan-check.sh", str(d), cwd=repo)
    assert "OVERLAPS KAN-1 KAN-2: a.ts" in lines(r)


def test_plan_file_with_h3_ticket_sections(repo, run_script):
    p = write_plan(repo, {
        "E1-T1": ticket(owns=["src/a.ts"]),
        "E1-T2": ticket(owns=["src/a.ts"], depends=["E1-T1"]),
    })
    r = run_script("plan-check.sh", str(p), cwd=repo)
    assert "OVERLAPS E1-T1 E1-T2: src/a.ts" in lines(r)
    assert "CRITICAL-PATH E1-T1 -> E1-T2" in lines(r)


def test_touches_shared_by_three_is_a_hotspot_not_a_failure(repo, run_script):
    d = write_dir(repo, {
        f"E1-T{i}": ticket(owns=[f"src/m{i}.ts"], touches=["src/registry.ts (append)"])
        for i in (1, 2, 3)
    })
    r = run_script("plan-check.sh", str(d), cwd=repo)
    assert r.returncode == 0, r.stdout
    assert any(l.startswith("HOTSPOTS shared: src/registry.ts") and "E1-T3" in l for l in lines(r))


def test_touches_shared_by_two_is_not_a_hotspot(repo, run_script):
    d = write_dir(repo, {
        f"E1-T{i}": ticket(owns=[f"src/m{i}.ts"], touches=["src/registry.ts"]) for i in (1, 2)
    })
    r = run_script("plan-check.sh", str(d), cwd=repo)
    assert not [l for l in lines(r) if l.startswith("HOTSPOTS")]


def test_churned_path_is_a_hotspot(repo, run_script):
    for i in range(4):
        (repo / "src").mkdir(exist_ok=True)
        (repo / "src" / "hot.ts").write_text(f"x{i}\n", encoding="utf-8")
        git("add", "src/hot.ts", cwd=repo)
        git("commit", "-q", "-m", f"c{i}", cwd=repo)
    d = write_dir(repo, {
        "E1-T1": ticket(owns=["src/"]),
        "E1-T2": ticket(owns=["lib/cold.ts"]),
    })
    r = run_script("plan-check.sh", str(d), "--churn", "3", cwd=repo)
    assert r.returncode == 0, r.stdout
    churn = [l for l in lines(r) if l.startswith("HOTSPOTS churn")]
    assert churn == ["HOTSPOTS churn: src (4 of the last 200 commits)"]
    r = run_script("plan-check.sh", str(d), cwd=repo)
    assert not [l for l in lines(r) if l.startswith("HOTSPOTS churn")]


def test_protected_hit_with_protected_no_fails(repo, run_script):
    cfg = repo / ".claude" / "workflow"
    cfg.mkdir(parents=True)
    (cfg / "config.md").write_text(
        "# Config\n\n## Protected paths\n\n- `src/auth/**` — login\n- `db/*.sql`\n- `lib/secure/**`\n\n## Other\n- `x/**`\n",
        encoding="utf-8",
    )
    d = write_dir(repo, {
        "E1-T1": ticket(owns=["src/auth/login.ts"], protected="no"),
        "E1-T2": ticket(owns=["db/001.sql"], protected="yes"),
        "E1-T3": ticket(owns=["lib/"], protected="no"),
        "E1-T4": ticket(owns=["x/y.ts"], protected="no"),
    })
    r = run_script("plan-check.sh", str(d), cwd=repo)
    assert r.returncode == 1
    prot = [l for l in lines(r) if l.startswith("PROTECTED")]
    assert [l.split(":")[0] for l in prot] == ["PROTECTED E1-T1", "PROTECTED E1-T3"]
    assert lines(r)[-1] == "PLAN FAIL 2"


def test_protected_override_flag(repo, run_script):
    d = write_dir(repo, {"E1-T1": ticket(owns=["lib/x.ts"], touches=["core/y.ts"], protected="no")})
    r = run_script("plan-check.sh", str(d), "--protected", "core/** other/**", cwd=repo)
    assert r.returncode == 1
    assert any(l.startswith("PROTECTED E1-T1: core/y.ts") for l in lines(r))


def test_no_protected_section_means_none(repo, run_script):
    d = write_dir(repo, {"E1-T1": ticket(owns=["src/auth/a.ts"], protected="no")})
    r = run_script("plan-check.sh", str(d), cwd=repo)
    assert r.returncode == 0, r.stdout


def test_critical_path_is_the_longest_chain(repo, run_script):
    d = write_dir(repo, {
        "A-1": ticket(owns=["a"]),
        "A-2": ticket(owns=["b"], depends=["A-1"]),
        "A-3": ticket(owns=["c"], depends=["A-2"]),
        "A-4": ticket(owns=["d"], depends=["A-1"]),
    })
    r = run_script("plan-check.sh", str(d), cwd=repo)
    assert "CRITICAL-PATH A-1 -> A-2 -> A-3" in lines(r)


def test_dependency_cycle_fails(repo, run_script):
    d = write_dir(repo, {
        "A-1": ticket(owns=["a"], depends=["A-2"]),
        "A-2": ticket(owns=["b"], depends=["A-1"]),
    })
    r = run_script("plan-check.sh", str(d), cwd=repo)
    assert r.returncode == 1
    assert any(l.startswith("DEPENDS cycle:") for l in lines(r))
    assert lines(r)[-1].startswith("PLAN FAIL")


def test_unknown_dependency_fails(repo, run_script):
    d = write_dir(repo, {"A-1": ticket(owns=["a"], depends=["Z-9"])})
    r = run_script("plan-check.sh", str(d), cwd=repo)
    assert r.returncode == 1
    assert "DEPENDS A-1: unknown key Z-9" in lines(r)


def test_sweep_over_too_many_top_level_dirs(repo, run_script):
    d = write_dir(repo, {"A-1": ticket(owns=["a/x", "b/x", "c/x", "d/x"])})
    r = run_script("plan-check.sh", str(d), cwd=repo)
    assert r.returncode == 0, r.stdout
    assert any(l.startswith("SWEEPS A-1: 4 top-level dirs") for l in lines(r))
    r = run_script("plan-check.sh", str(d), "--max-dirs", "4", cwd=repo)
    assert not [l for l in lines(r) if l.startswith("SWEEPS")]


def test_list_prints_one_tickets_paths(repo, run_script):
    d = write_dir(repo, {"A-1": ticket(owns=["src/a.ts (x)", "`lib/`"], touches=["reg.ts"])})
    r = run_script("plan-check.sh", "--list", str(d / "A-1.md"), cwd=repo)
    assert r.returncode == 0, r.stderr
    assert lines(r) == ["OWNS src/a.ts", "OWNS lib", "TOUCHES reg.ts"]


def test_usage(repo, run_script):
    assert run_script("plan-check.sh", cwd=repo).returncode == 64
    assert run_script("plan-check.sh", "nope.md", cwd=repo).returncode == 64
    assert run_script("plan-check.sh", "x", "--bogus", cwd=repo).returncode == 64
