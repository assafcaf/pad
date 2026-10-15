"""Multi-package knowledge layer: a repo level plus one level per package.

Repo level: `CONTEXT.md` and `.claude/workflow/project.md` (what the repo is, a Packages table,
shared commands, cross-package overlaps). Package level: `<pkg>/PROJECT.md` (required) and
`<pkg>/CONTEXT.md` (optional), beside the package's code. config.md's Project knowledge section
lists the packages on a `Packages:` line, as paths or a glob; without that line the repo is a
single package, as before.

knowledge-paths.sh checks every package file the same way as the repo's: it exists (PROJECT.md),
it is under its ceiling, and every path it names resolves.
"""
from __future__ import annotations

from pathlib import Path

import pytest

SCRIPT = "knowledge-paths.sh"
SKILL = "claude/skills/knowledge-layer/SKILL.md"
FORMAT = "claude/skills/knowledge-layer/PROJECT-FORMAT.md"


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _layer(root: Path, packages: str | None = "`service/`, `lab/`") -> None:
    line = f"Packages: {packages}\n\n" if packages else ""
    _write(root, ".claude/workflow/config.md", f"## Project knowledge\n\nMode: on\n\n{line}## Surfaces\n\n")
    _write(root, "CONTEXT.md", "# Glossary\n")
    _write(root, ".claude/workflow/project.md",
           "# Notes\n\n## Packages\n| Package | Owns |\n|---|---|\n| `service/` | API |\n| `lab/` | analysis |\n")
    _write(root, "service/api.py", "X = 1\n")
    _write(root, "lab/core.py", "Y = 1\n")
    _write(root, "service/PROJECT.md", "# service/\n\n## Module map\n| `service/api.py` | API |\n")
    _write(root, "service/CONTEXT.md", "# service/ terms\n")
    _write(root, "lab/PROJECT.md", "# lab/\n\n## Module map\n| `lab/core.py` | core |\n")


def _run(run_script, root: Path, env=None):
    return run_script(SCRIPT, "--root", root.as_posix(), cwd=root, env=env)


def test_a_multi_package_layer_whose_paths_resolve_passes(repo, run_script):
    """Also: a package's CONTEXT.md is optional (lab/ has none)."""
    _layer(repo)
    assert not (repo / "lab" / "CONTEXT.md").exists()
    r = _run(run_script, repo)
    assert r.returncode == 0, r.stdout


def test_a_package_without_its_project_md_fails(repo, run_script):
    _layer(repo)
    (repo / "lab" / "PROJECT.md").unlink()
    r = _run(run_script, repo)
    assert r.returncode == 1
    assert "lab/PROJECT.md is missing" in r.stdout


def test_a_dead_path_in_a_package_file_fails_naming_the_file(repo, run_script):
    _layer(repo)
    (repo / "service" / "api.py").unlink()
    r = _run(run_script, repo)
    assert r.returncode == 1
    assert "service/PROJECT.md names service/api.py" in r.stdout


def test_the_ceiling_applies_to_each_package_file(repo, run_script):
    _layer(repo)
    _write(repo, "lab/PROJECT.md", "# lab/\n" + "line\n" * 130)
    r = _run(run_script, repo)
    assert r.returncode == 1
    assert "lab/PROJECT.md is 131 lines, ceiling is 120" in r.stdout


@pytest.mark.slow
def test_a_glob_lists_the_packages(repo, run_script):
    _layer(repo, packages="`packages/*/`")
    for pkg in ("a", "b"):
        _write(repo, f"packages/{pkg}/x.py", "X = 1\n")
        _write(repo, f"packages/{pkg}/PROJECT.md", f"# {pkg}\n| `packages/{pkg}/x.py` | x |\n")
    assert _run(run_script, repo).returncode == 0
    (repo / "packages" / "b" / "PROJECT.md").unlink()
    r = _run(run_script, repo)
    assert "packages/b/PROJECT.md is missing" in r.stdout


def test_without_a_packages_line_package_files_are_not_required(repo, run_script):
    _layer(repo, packages=None)
    (repo / "lab" / "PROJECT.md").unlink()
    assert _run(run_script, repo).returncode == 0


def test_a_brace_pattern_is_not_a_path(repo, run_script):
    _layer(repo)
    _write(repo, "lab/PROJECT.md", "# lab/\n| `lab/core.py` | core |\n| `lab/grid/{a,b}.yaml` | grids |\n")
    assert _run(run_script, repo).returncode == 0


# --- prose --------------------------------------------------------------------------------------


def test_skill_works_per_package(payload_text):
    text = payload_text(SKILL)
    # scans and grills per package
    assert "one `knowledge-scanner` per package" in text
    assert "The grill runs once per package" in text
    # refreshes one package
    assert "/knowledge-layer refresh <package>" in text
    assert 'argument-hint: "[refresh [<package>]]"' in text
    # repairs per file
    assert "Repair works per file" in text
    # adopts a hand-written package layout
    assert "adopts" in text and "`Packages:` line" in text
    # readers load the repo level plus the packages their files touch
    assert "plus the package files of every package its task's Files touch" in text


def test_format_describes_the_package_level(payload_text):
    text = payload_text(FORMAT)
    assert "## Packages" in text
    assert "`<package>/PROJECT.md`" in text
