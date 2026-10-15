"""ledger.sh writes status and comments through the configured adapter, and keeps board.md.

    ledger.sh <KEY> status <to> "<comment>" [--run <id> --owner --branch --sha --evidence]

`gh` and `curl` are stubs on PATH that log their arguments, so these run with no network.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

CONFIG = """# Workflow config

## Tracker

- **Adapter:** `{adapter}`. Operations are in `.claude/workflow/trackers/{adapter}.md`.
- **Jira:** site `https://acme.atlassian.net`, cloudId `abc`, project `KAN`.
- **Statuses:** todo `To Do`, doing `In Progress`, review `In Review`, done `Done`. Transition
  ids: filled in by `/setup-workflow`.
"""

CURL = r"""#!/usr/bin/env bash
a="$*"
printf '%s | stdin: %s\n' "${a//$'\n'/\\n}" "$(cat)" >> "$STUB_LOG"
case "$*" in
  *"-X GET"*transitions*)
    printf '%s\n%s' '{"transitions":[{"id":"21","to":{"name":"In Progress"}},{"id":"31","to":{"name":"Done"}}]}' "${STUB_CODE:-200}" ;;
  *) printf '%s\n%s' '{}' "${STUB_CODE:-201}" ;;
esac
"""

GH = r"""#!/usr/bin/env bash
printf '%s\n' "$*" >> "$STUB_LOG"
exit "${STUB_EXIT:-0}"
"""


def _stub(dir_: Path, name: str, text: str) -> None:
    p = dir_ / name
    p.write_bytes(text.encode("utf-8"))
    os.chmod(p, 0o755)


@pytest.fixture
def stubs(tmp_path):
    d = tmp_path / "stubs"
    d.mkdir()
    _stub(d, "curl", CURL)
    _stub(d, "gh", GH)
    log = tmp_path / "stub.log"
    # Git for Windows' bash.exe puts /mingw64/bin ahead of the PATH it is given, so a stub on
    # PATH alone loses to the real curl. BASH_ENV runs after that, inside the script's shell.
    posix = d.as_posix()
    if len(posix) > 1 and posix[1] == ":":
        posix = "/" + posix[0].lower() + posix[2:]
    rc = tmp_path / "stub-env.sh"
    rc.write_bytes(f'PATH="{posix}:$PATH"\n'.encode("utf-8"))
    env = {"BASH_ENV": rc.as_posix(), "STUB_LOG": log.as_posix()}
    return env, log


def _configure(repo: Path, adapter: str) -> None:
    cfg = repo / ".claude" / "workflow" / "config.md"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_bytes(CONFIG.format(adapter=adapter).encode("utf-8"))


def _secrets(repo: Path) -> None:
    s = repo / ".work" / "secrets" / "jira.env"
    s.parent.mkdir(parents=True, exist_ok=True)
    s.write_bytes(b"JIRA_EMAIL=me@example.com\nJIRA_API_TOKEN='tok123'\n")


def _calls(log: Path) -> list[str]:
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def _last(r) -> str:
    return r.stdout.strip().splitlines()[-1]


# --- github ------------------------------------------------------------------------------------

def test_github_done_closes_issue_and_comments(repo, stubs, run_script):
    env, log = stubs
    _configure(repo, "github")
    r = run_script("ledger.sh", "#12", "status", "done", "merged abc1234", cwd=repo, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == "LEDGER OK #12 done"
    calls = _calls(log)
    assert calls[0] == "issue close 12 --reason completed"
    assert calls[1] == "issue comment 12 --body merged abc1234"


def test_github_doing_adds_in_progress_label(repo, stubs, run_script):
    env, log = stubs
    _configure(repo, "github")
    r = run_script("ledger.sh", "7", "status", "doing", "picked up", cwd=repo, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _calls(log)[0] == "issue edit 7 --add-label in-progress --remove-label in-review"


def test_github_failure_is_ledger_fail(repo, stubs, run_script):
    env, _ = stubs
    _configure(repo, "github")
    r = run_script("ledger.sh", "7", "comment", "x", cwd=repo, env={**env, "STUB_EXIT": "1"})
    assert r.returncode == 1
    assert _last(r).startswith("LEDGER FAIL 7: gh comment")


# --- jira --------------------------------------------------------------------------------------

def test_jira_done_takes_the_transition_to_the_configured_name(repo, stubs, run_script):
    env, log = stubs
    _configure(repo, "jira")
    _secrets(repo)
    r = run_script("ledger.sh", "KAN-5", "status", "done", "merged \"x\"", cwd=repo, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _last(r) == "LEDGER OK KAN-5 done"
    calls = _calls(log)
    assert len(calls) == 3
    assert "-X GET" in calls[0] and "https://acme.atlassian.net/rest/api/3/issue/KAN-5/transitions" in calls[0]
    assert "-X POST" in calls[1] and '{"transition":{"id":"31"}}' in calls[1]
    assert "/issue/KAN-5/comment" in calls[2] and '"text": "merged \\"x\\""' in calls[2].replace('"text":"', '"text": "')
    # The credentials reach curl on stdin, never on its command line.
    assert all(c.endswith('stdin: user = "me@example.com:tok123"') for c in calls), calls
    assert all("tok123" not in c.split(" | stdin: ")[0] for c in calls)
    assert "tok123" not in r.stdout + r.stderr


def test_jira_without_credentials_fails_naming_the_file(repo, stubs, run_script):
    env, log = stubs
    _configure(repo, "jira")
    r = run_script("ledger.sh", "KAN-5", "comment", "x", cwd=repo, env=env)
    assert r.returncode == 1
    assert "LEDGER FAIL KAN-5: no credentials" in _last(r)
    assert ".work/secrets/jira.env" in _last(r).replace("\\", "/")
    assert _calls(log) == []


def test_jira_http_error_is_ledger_fail(repo, stubs, run_script):
    env, _ = stubs
    _configure(repo, "jira")
    _secrets(repo)
    r = run_script("ledger.sh", "KAN-5", "status", "doing", "x", cwd=repo,
                   env={**env, "STUB_CODE": "401"})
    assert r.returncode == 1
    assert "HTTP 401" in _last(r)


def test_unknown_adapter_fails(repo, run_script):
    _configure(repo, "trello")
    r = run_script("ledger.sh", "T-1", "comment", "x", cwd=repo)
    assert r.returncode == 1
    assert "unknown tracker adapter 'trello'" in _last(r)


# --- board -------------------------------------------------------------------------------------

def _board(repo: Path, run: str = "E1") -> list[str]:
    p = repo / ".work" / "runs" / run / "board.md"
    return [l for l in p.read_text(encoding="utf-8").splitlines() if l.startswith("| E")]


def test_board_row_written_then_refreshed_keeping_fields(repo, worktree, run_script):
    d = repo / ".work" / "tickets" / "E1"
    d.mkdir(parents=True)
    for k in ("E1-T1", "E1-T2"):
        (d / f"{k}.md").write_bytes(f"---\nkey: {k}\nstatus: todo\n---\n".encode())
    wt = worktree(repo, "b")
    r = run_script("ledger.sh", "E1-T1", "status", "doing", "start", "--run", "E1",
                   "--owner", "a1", "--branch", "task/E1-T1", cwd=wt)
    assert r.returncode == 0, r.stdout + r.stderr
    run_script("ledger.sh", "E1-T2", "status", "doing", "start", "--run", "E1", cwd=wt)
    r = run_script("ledger.sh", "E1-T1", "status", "done", "merged", "--run", "E1",
                   "--sha", "abc1234", "--evidence", ".work/runs/E1/E1-T1.md", cwd=wt)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _board(repo) == [
        "| E1-T1 | a1 | done | task/E1-T1 | abc1234 | .work/runs/E1/E1-T1.md |",
        "| E1-T2 | - | doing | - | - | - |",
    ]
    assert not (wt / ".work").exists()
