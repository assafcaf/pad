"""Rules: one file per rule under .claude/workflow/rules/, loaded by the agents it names and
enforced at the one point its kind is wired to.

    rules.sh for <agent>         the guidance of every rule whose applies-to names <agent>
    rules.sh list <kind>         name, check path and claim of each rule of that kind
    rules.sh validate            every rule file is well formed

weakened-tests.sh runs the test-removal rules' checks; task-submit.sh runs the test-authoring
rules' checks over added test lines. PAD_RULES_DIR points the scripts at a fixture folder.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from conftest import PAYLOAD, git

RULES = PAYLOAD / "claude" / "workflow" / "rules"
AGENTS = PAYLOAD / "claude" / "agents"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "rules"


def _commit(wt: Path, files: dict[str, str | None], msg: str) -> str:
    for rel, text in files.items():
        p = wt / rel
        if text is None:
            git("rm", "-q", rel, cwd=wt)
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        git("add", rel, cwd=wt)
    git("commit", "-q", "-m", msg, cwd=wt)
    return git("rev-parse", "HEAD", cwd=wt)


def _rules_copy(tmp_path: Path, extra: dict[str, str] | None = None) -> Path:
    """A copy of PAD's rules folder, plus extra files, for a repo that adds its own rules."""
    d = tmp_path / "rules"
    shutil.copytree(RULES, d)
    for name, text in (extra or {}).items():
        (d / name).write_text(text, encoding="utf-8")
    return d


def _rule(name: str, kind: str, applies: str, check: str | None = None, body: str = "Do X.") -> str:
    lines = ["---", f"name: {name}", f"kind: {kind}", f"applies-to: {applies}"]
    if check:
        lines.append(f"check: {check}")
    return "\n".join(lines + ["---", "", body, ""])


# --- rules.sh ----------------------------------------------------------------------------------


@pytest.mark.slow
def test_every_payload_rule_file_validates(run_script, repo):
    r = run_script("rules.sh", "validate", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1].startswith("RULES OK")


def test_pad_ships_the_agreed_rules():
    names = {p.stem for p in RULES.glob("*.md")}
    assert {
        "code-deleted", "same-name-readded", "ported-from",
        "no-fixed-sleeps", "platform-neutral", "gone-means-untracked", "no-pinned-aggregates",
        "no-full-suite-in-agents", "register-by-file", "append-only-sorted",
    } <= names


def test_for_prints_only_the_rules_that_name_the_agent(run_script, repo, tmp_path):
    d = tmp_path / "r"
    d.mkdir()
    (d / "a.md").write_text(_rule("a", "practice", "owner", body="Alpha guidance."), encoding="utf-8")
    (d / "b.md").write_text(_rule("b", "practice", "test-designer", body="Beta guidance."), encoding="utf-8")
    r = run_script("rules.sh", "for", "owner", cwd=repo, env={"PAD_RULES_DIR": str(d)})
    assert r.returncode == 0, r.stderr
    assert "Alpha guidance." in r.stdout
    assert "Beta guidance." not in r.stdout


@pytest.mark.slow
def test_a_repo_rule_dropped_in_the_folder_is_live_for_its_agent(run_script, repo, tmp_path):
    example = (FIXTURES / "restore-global-state.md").read_text(encoding="utf-8")
    d = _rules_copy(tmp_path, {"restore-global-state.md": example})
    env = {"PAD_RULES_DIR": str(d)}
    r = run_script("rules.sh", "for", "owner", cwd=repo, env=env)
    assert "restore-global-state" in r.stdout
    assert run_script("rules.sh", "validate", cwd=repo, env=env).returncode == 0


@pytest.mark.slow
@pytest.mark.parametrize("text, fail", [
    (_rule("x", "practice", "owner, nobody"), "RULES FAIL x: applies-to names nobody"),
    (_rule("x", "vibes", "owner"), "RULES FAIL x: kind vibes"),
    (_rule("x", "test-removal", "orchestrator", check="x.sh"), "RULES FAIL x: check x.sh"),
    (_rule("x", "test-removal", "orchestrator"), "RULES FAIL x: test-removal needs a check"),
    ("---\nname: x\nkind: practice\n---\n\nBody.\n", "RULES FAIL x: missing applies-to"),
], ids=["unknown-agent", "unknown-kind", "missing-check-script", "removal-without-check",
        "missing-field"])
def test_validate_rejects_a_malformed_rule(run_script, repo, tmp_path, text, fail):
    d = _rules_copy(tmp_path, {"x.md": text})
    r = run_script("rules.sh", "validate", cwd=repo, env={"PAD_RULES_DIR": str(d)})
    assert r.returncode == 1
    assert fail in r.stdout


def test_every_agent_a_rule_can_name_loads_its_rules_at_start():
    loaders = [p.stem for p in AGENTS.glob("*.md") if f"rules.sh for {p.stem}" in p.read_text(encoding="utf-8")]
    for agent in ("owner", "test-designer",
                  "memory-curator", "knowledge-scanner"):
        assert agent in loaders, agent
    skill = (PAYLOAD / "claude" / "skills" / "pad-run" / "SKILL.md").read_text(encoding="utf-8")
    assert "rules.sh for orchestrator" in skill


# --- weakened-tests.sh: test-removal rules ---------------------------------------------------


def _weak(run_script, repo, base, head, *extra, env=None):
    return run_script("weakened-tests.sh", *extra, base, head, cwd=repo, env=env)


def _module_and_test(repo: Path) -> str:
    return _commit(repo, {
        "safe/cli.py": "def main():\n    return 0\n",
        "tests/test_safe_cli.py": "from safe.cli import main\n\n\ndef test_main():\n    assert main() == 0\n",
    }, "base: module and its test")


def _claims(tmp_path: Path, text: str) -> str:
    p = tmp_path / "claims.txt"
    p.write_text(text, encoding="utf-8")
    return str(p)


@pytest.mark.slow
def test_deleting_a_test_with_its_module_is_explained_and_claims_are_checked(
    run_script, repo, tmp_path
):
    """One `delete safe` commit: code-deleted explains it; no rules, a wrong or missing claim fail."""
    base = _module_and_test(repo)
    head = _commit(repo, {"safe/cli.py": None, "tests/test_safe_cli.py": None}, "delete safe")

    r = _weak(run_script, repo, base, head)
    assert r.returncode == 0, r.stdout
    assert "tests/test_safe_cli.py::test_main  code-deleted" in r.stdout

    empty = tmp_path / "none"
    empty.mkdir()
    assert _weak(run_script, repo, base, head, env={"PAD_RULES_DIR": str(empty)}).returncode == 1

    claims = _claims(tmp_path, "tests/test_safe_cli.py::test_main | code-deleted | safe/ is gone\n")
    r = _weak(run_script, repo, base, head, "--claims", claims)
    assert r.returncode == 0, r.stdout

    for text in ("tests/test_safe_cli.py::test_main | ported-from | moved\n", ""):
        r = _weak(run_script, repo, base, head, "--claims", _claims(tmp_path, text))
        assert r.returncode == 3, (text, r.stdout)
        assert "MISMATCH tests/test_safe_cli.py::test_main" in r.stdout


def _moved_module(repo: Path) -> str:
    (repo / "lab").mkdir()
    git("mv", "safe/cli.py", "lab/cli.py", cwd=repo)
    return _commit(repo, {"tests/test_safe_cli.py": None}, "move safe, drop its test")


def _test_only_dropped(repo: Path) -> str:
    return _commit(repo, {"tests/test_safe_cli.py": None}, "drop the test only")


def _ported(repo: Path) -> str:
    return _commit(repo, {
        "tests/test_safe_cli.py": None,
        "tests/lab/test_cli.py": (
            "from safe.cli import main\n\n\n"
            "# ported-from: tests/test_safe_cli.py::test_main\n"
            "def test_lab_main():\n    assert main() == 0\n"
        ),
    }, "port the test")


def _readded(repo: Path) -> str:
    return _commit(repo, {
        "tests/test_safe_cli.py": None,
        "tests/test_cli_moved.py": "from safe.cli import main\n\n\ndef test_main():\n    assert main() == 0\n",
    }, "move the test")


@pytest.mark.parametrize("change, code, needles", [
    pytest.param(_moved_module, 1, ("removed tests:", "tests/test_safe_cli.py::test_main"),
                 id="moved-module-does-not-explain", marks=pytest.mark.slow),
    pytest.param(_test_only_dropped, 1, (), id="module-stays-not-explained",
                 marks=pytest.mark.slow),
    pytest.param(_ported, 0, ("tests/test_safe_cli.py::test_main  ported-from",),
                 id="ported-from-explains", marks=pytest.mark.slow),
    pytest.param(_readded, 0, (), id="re-added-under-its-name-passes"),
])
def test_a_removed_test_is_explained_only_by_a_rule(run_script, repo, change, code, needles):
    base = _module_and_test(repo)
    head = change(repo)
    r = _weak(run_script, repo, base, head)
    assert r.returncode == code, r.stdout
    for needle in needles:
        assert needle in r.stdout


def test_a_todo_in_product_code_is_reported_on_its_own_line(run_script, repo):
    base = git("rev-parse", "HEAD", cwd=repo)
    head = _commit(repo, {"src/impl.py": "X = 1  # TODO: tune\n"}, "impl")
    r = _weak(run_script, repo, base, head)
    assert r.returncode == 1
    assert "weakened-tests: added TODO:" in r.stdout
    assert "skip/xfail" not in r.stdout


# --- task-submit.sh: test-authoring rules ----------------------------------------------------


def _submit_with(run_script, repo, worktree, files: dict[str, str]):
    epic = git("rev-parse", "HEAD", cwd=repo)
    wt = worktree(repo, "t-auth")
    git("reset", "-q", "--hard", epic, cwd=wt)
    red = _commit(wt, files, "test(T-1): o1 [red]")
    return run_script("task-submit.sh", epic, red, red, "--test-paths", "tests/", cwd=wt)


@pytest.mark.parametrize("files, verdict", [
    pytest.param(
        {"tests/test_x.py": "import time\n\n\ndef test_x():\n    time.sleep(2.0)\n    assert False\n"},
        "SUBMIT FAIL test-authoring: no-fixed-sleeps", id="fixed-sleep-fails"),
    pytest.param(
        {"tests/test_x.py": "import time\n\n\ndef test_x():\n    time.sleep(0.05)\n    assert False\n"},
        "SUBMIT OK", id="short-poll-sleep-allowed", marks=pytest.mark.slow),
    pytest.param(
        {"tests/test_x.py": "def test_x():\n    assert False\n",
         "src/poll.py": "import time\ntime.sleep(5)\n"},
        "SUBMIT OK", id="sleep-in-product-code-allowed", marks=pytest.mark.slow),
    pytest.param(
        {"tests/test_x.py": "from pathlib import Path\n\n\ndef test_x():\n    assert not Path('safe').exists()\n"},
        "gone-means-untracked", id="path-gone-fails", marks=pytest.mark.slow),
    pytest.param(
        {"tests/test_x.py": (
            "import sys\nimport pytest\n\n\n"
            "@pytest.mark.skipif(sys.platform == 'win32', reason='posix')\n"
            "def test_x():\n    assert False\n")},
        "platform-neutral", id="platform-skip-fails", marks=pytest.mark.slow),
])
def test_test_authoring_rules_judge_the_added_test_lines(run_script, repo, worktree, files, verdict):
    r = _submit_with(run_script, repo, worktree, files)
    last = r.stdout.strip().splitlines()[-1]
    if verdict == "SUBMIT OK":
        assert last == "SUBMIT OK", r.stdout
    else:
        assert r.returncode == 1, r.stdout
        assert last.startswith("SUBMIT FAIL") and verdict in last, r.stdout
