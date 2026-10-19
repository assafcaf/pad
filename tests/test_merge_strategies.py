"""E2-T2: merge-strategies.sh validates strategy file pairs and the config's `Merge strategy:` line
(O15, O24), and preflight.sh fails its `merge-strategy` check on a repo where validate fails.

A strategy is `<name>.md` plus its script, in the strategies folder (PAD_STRATEGIES_DIR here;
`.claude/workflow/merge-strategies/` beside bin/ by default). The .md has frontmatter `name`,
`script` (a file name beside it), `description` and `options` (comma-separated `opt=default`
entries), then the "when to use" body. The config line is `Merge strategy: <name> [opt=val ...]`
in .claude/workflow/config.md, read from the working directory. `validate` prints
`STRATEGY FAIL <name>: <why>` per problem and exits 1.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from test_preflight import assert_failed, config_md, install

SCRIPT = "merge-strategies.sh"


def strategy_md(name: str, script: str | None = None, omit: tuple[str, ...] = (),
                options: str = "max=4") -> str:
    fields = {
        "name": name,
        "script": script if script is not None else f"{name}.sh",
        "description": f"The {name} strategy.",
        "options": options,
    }
    head = [f"{k}: {v}" for k, v in fields.items() if k not in omit]
    return "\n".join(["---", *head, "---", "", "When to use: always.", ""])


def make_dir(d: Path, *names: str) -> Path:
    """A strategies folder with a valid pair per name."""
    d.mkdir(parents=True, exist_ok=True)
    for n in names:
        (d / f"{n}.md").write_text(strategy_md(n), encoding="utf-8")
        (d / f"{n}.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    return d


def write_config(cwd: Path, line: str | None) -> None:
    cfg = cwd / ".claude" / "workflow" / "config.md"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text("# Workflow config\n\n## Execution\n\n"
                   + (f"{line}\n" if line is not None else ""), encoding="utf-8")


@pytest.fixture
def validate(run_script, tmp_path):
    """validate(strategies_dir, config_line=None) -> result; runs in a scratch dir."""
    cwd = tmp_path / "work"
    cwd.mkdir()

    def run(d: Path, line: str | None = None):
        write_config(cwd, line)
        return run_script(SCRIPT, "validate", cwd=cwd, env={"PAD_STRATEGIES_DIR": d.as_posix()})

    return run


def fail_lines(result) -> list[str]:
    return [ln for ln in result.stdout.splitlines() if ln.startswith("STRATEGY FAIL ")]


def preflight_in(repo: Path, run_script, tmp_path: Path, config: str | None, *names: str,
                 unlink: str | None = None):
    """Install PAD into repo, add strategies under its merge-strategies folder, run preflight."""
    install(repo, config=config)
    d = make_dir(repo / ".claude" / "workflow" / "merge-strategies", *names)
    if unlink:
        (d / unlink).unlink()
    home = tmp_path / "home"
    home.mkdir()
    return run_script("preflight.sh", cwd=repo, env={"HOME": home.as_posix()})


# --- O15 ---------------------------------------------------------------------------------------


def test_o15_valid_strategy_pairs_validate_clean(validate, tmp_path):
    r = validate(make_dir(tmp_path / "s", "alpha", "beta"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert fail_lines(r) == []


@pytest.mark.parametrize("field", ["name", "script", "description"])
def test_o15_a_strategy_file_missing_a_field_fails_naming_the_field(validate, tmp_path, field):
    d = make_dir(tmp_path / "s", "alpha")
    (d / "alpha.md").write_text(strategy_md("alpha", omit=(field,)), encoding="utf-8")
    r = validate(d)
    assert r.returncode == 1, r.stdout + r.stderr
    got = fail_lines(r)
    assert len(got) == 1 and got[0].startswith("STRATEGY FAIL alpha: ") and field in got[0], r.stdout


def test_o15_a_strategy_whose_script_is_missing_fails_naming_the_script(validate, tmp_path):
    d = make_dir(tmp_path / "s", "alpha")
    (d / "alpha.sh").unlink()
    r = validate(d)
    assert r.returncode == 1, r.stdout + r.stderr
    got = fail_lines(r)
    assert len(got) == 1 and got[0].startswith("STRATEGY FAIL alpha: ") and "alpha.sh" in got[0], r.stdout


def test_o15_a_duplicate_strategy_name_fails(validate, tmp_path):
    d = make_dir(tmp_path / "s", "one", "two")
    (d / "one.md").write_text(strategy_md("two", script="one.sh"), encoding="utf-8")
    r = validate(d)
    assert r.returncode == 1, r.stdout + r.stderr
    assert any(ln.startswith("STRATEGY FAIL two: ") and "duplicate" in ln for ln in fail_lines(r)), r.stdout


def test_o15_each_problem_prints_its_own_fail_line(validate, tmp_path):
    d = make_dir(tmp_path / "s", "alpha", "beta")
    (d / "alpha.sh").unlink()
    (d / "beta.md").write_text(strategy_md("beta", omit=("description",)), encoding="utf-8")
    r = validate(d)
    assert r.returncode == 1, r.stdout + r.stderr
    got = fail_lines(r)
    assert any(ln.startswith("STRATEGY FAIL alpha: ") for ln in got), r.stdout
    assert any(ln.startswith("STRATEGY FAIL beta: ") for ln in got), r.stdout


def test_o15_a_config_option_the_strategy_does_not_declare_fails_naming_it(validate, tmp_path):
    r = validate(make_dir(tmp_path / "s", "alpha"), "Merge strategy: alpha bogus=1")
    assert r.returncode == 1, r.stdout + r.stderr
    got = fail_lines(r)
    assert len(got) == 1 and got[0].startswith("STRATEGY FAIL alpha: ") and "bogus" in got[0], r.stdout


def test_o15_a_config_option_the_strategy_declares_is_accepted(validate, tmp_path):
    r = validate(make_dir(tmp_path / "s", "alpha"), "Merge strategy: alpha max=2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert fail_lines(r) == []


def test_o15_a_config_line_naming_no_strategy_fails(validate, tmp_path):
    r = validate(make_dir(tmp_path / "s", "alpha"), "Merge strategy: nosuch")
    assert r.returncode == 1, r.stdout + r.stderr
    assert any(ln.startswith("STRATEGY FAIL nosuch: ") for ln in fail_lines(r)), r.stdout


def test_o15_preflight_fails_its_merge_strategy_check_on_an_invalid_strategy(repo, run_script, tmp_path):
    r = preflight_in(repo, run_script, tmp_path, None, "alpha", unlink="alpha.sh")
    assert_failed(r, "merge-strategy", "alpha")


def test_o15_preflight_fails_its_merge_strategy_check_on_a_bad_config_line(repo, run_script, tmp_path):
    cfg = config_md() + "\nMerge strategy: alpha bogus=1\n"
    r = preflight_in(repo, run_script, tmp_path, cfg, "alpha")
    assert_failed(r, "merge-strategy", "alpha", "bogus")


# --- O24 ---------------------------------------------------------------------------------------


def test_o24_a_strategy_file_named_dynamic_is_a_reserved_name(validate, tmp_path):
    r = validate(make_dir(tmp_path / "s", "alpha", "dynamic"))
    assert r.returncode == 1, r.stdout + r.stderr
    assert "STRATEGY FAIL dynamic: reserved name" in r.stdout.splitlines(), r.stdout


def test_o24_a_config_line_merge_strategy_dynamic_is_accepted(validate, tmp_path):
    r = validate(make_dir(tmp_path / "s", "alpha"), "Merge strategy: dynamic")
    assert r.returncode == 0, r.stdout + r.stderr
    assert fail_lines(r) == []
