"""E3-T1 O1: host-setup.sh writes the gitignored host.md.

`host-setup.sh [--cap <n%|nGB>]` run in a repo writes `.claude/workflow/host.md` with `OS:`,
`Memory total:`, `Memory cap:` (85% unless given) and `Self-test:` (the result of the
containment self-test, `PAD_SELF_TEST_CMD` when set, else `pad-proc.sh self-test`; its last
line is recorded), and makes `.gitignore` cover the file. A failed self-test exits non-zero with
the reason on stderr. `PAD_MEMORY_TOTAL_GB` stands in for the machine's total memory.
"""
from __future__ import annotations

import subprocess

import pytest

from conftest import BASH, BIN, git
from test_pad_proc import clean_env, posix

SETUP = (BIN / "host-setup.sh").as_posix()
OK = "echo 'SELF-TEST containment ok process-group'"


def setup(repo, *args, selftest=OK, total="16"):
    env = clean_env(PAD_MEMORY_TOTAL_GB=total, PAD_SELF_TEST_CMD=selftest)
    return subprocess.run([BASH, SETUP, *args], cwd=str(repo), env=env, capture_output=True,
                          text=True, timeout=120)


def host_md(repo):
    return (repo / ".claude" / "workflow" / "host.md").read_text(encoding="utf-8")


def test_o1_host_md_records_os_memory_total_default_cap_and_the_self_test_result(repo):
    r = setup(repo)
    assert r.returncode == 0, r.stderr
    text = host_md(repo)
    lines = dict(l.split(":", 1) for l in text.splitlines() if ":" in l)
    assert lines["OS"].strip() != ""
    assert lines["Memory total"].split()[0] in ("16", "16.0")
    assert lines["Memory cap"].strip() == "85%"
    assert "containment ok" in lines["Self-test"]


def test_o1_an_operator_percentage_becomes_the_memory_cap(repo):
    assert setup(repo, "--cap", "70%").returncode == 0
    assert "Memory cap: 70%" in host_md(repo)


def test_o1_an_operator_gb_figure_becomes_the_memory_cap(repo):
    assert setup(repo, "--cap", "12GB").returncode == 0
    assert "Memory cap: 12GB" in host_md(repo)


def test_o1_host_md_is_gitignored(repo):
    assert setup(repo).returncode == 0
    ignored = subprocess.run(["git", "check-ignore", "-q", ".claude/workflow/host.md"],
                             cwd=str(repo)).returncode
    assert ignored == 0
    git("add", "-A", cwd=repo)
    assert ".claude/workflow/host.md" not in git("diff", "--cached", "--name-only", cwd=repo)


@pytest.mark.slow
def test_o1_running_setup_twice_does_not_duplicate_the_gitignore_entry(repo):
    assert setup(repo).returncode == 0
    assert setup(repo).returncode == 0
    ignore = (repo / ".gitignore").read_text(encoding="utf-8")
    assert sum("host.md" in l for l in ignore.splitlines()) == 1


def test_o1_a_failing_self_test_stops_setup_with_the_reason(repo):
    r = setup(repo, selftest="echo 'a grandchild survived: pid 4242' >&2; exit 1")
    assert r.returncode != 0
    assert "grandchild survived" in r.stderr + r.stdout
