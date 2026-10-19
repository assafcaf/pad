"""E2-T8: merge.sh queues READY tickets, drains the queue through the selected strategy, checks the
contract after every pass and reports status (O1, O2, O4, O16, O23).

    merge.sh --run <id> --ready <KEY> <TASK_HEAD> <RED>
    merge.sh --run <id> --status

Run from the main checkout; the epic worktree is `<main>/.claude/worktrees/<id>`, the run's files
are in `<main>/.work/runs/<id>/`. The strategies here are fixtures under PAD_STRATEGIES_DIR: each
logs its name, option and queue keys to `log`, then answers per the word in `mode`:
reject | silent (no result line) | commit (commits to the epic, prints MERGED) | first-only |
mixed (first ticket CONFLICT, the rest REJECTED). While `hold` exists the strategy blocks.
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

import pytest

from conftest import BASH, BIN, git

RUN = "R1"
BAD1 = "0" * 40
BAD2 = "deadbeef" * 5

SCRIPT = """#!/usr/bin/env bash
D="{d}"
in="$(cat)"
echo "{name} max=${{PAD_OPT_MAX-unset}} keys=$(printf '%s\\n' "$in" | awk '{{print $1}}' | tr '\\n' ',')" >> "$D/log"
if [ -e "$D/hold" ]; then
  : > "$D/held"
  for _ in $(seq 1 1200); do [ -e "$D/hold" ] || break; sleep 0.1; done
fi
mode="$(cat "$D/mode" 2>/dev/null || echo reject)"
i=0
while read -r k h r; do
  [ -n "$k" ] || continue
  i=$((i + 1))
  case "$mode" in
    reject) echo "REJECTED $k: fixture" ;;
    silent) ;;
    first-only) [ "$i" -eq 1 ] && echo "REJECTED $k: fixture" ;;
    mixed) if [ "$i" -eq 1 ]; then echo "CONFLICT $k: a.txt"; else echo "REJECTED $k: fixture"; fi ;;
    commit)
      git -C "$PAD_EPIC_WORKTREE" commit -q --allow-empty -m "sneaky $k"
      echo "MERGED $k $(git -C "$PAD_EPIC_WORKTREE" rev-parse HEAD)" ;;
  esac
done <<<"$in"
exit 0
"""


class Env:
    def __init__(self, repo: Path, tmp: Path, run_script):
        self.repo = repo
        self.run_script = run_script
        self.sdir = tmp / "strategies"
        self.sdir.mkdir()
        self.run_dir = repo / ".work" / "runs" / RUN
        self.run_dir.mkdir(parents=True)
        cfg = repo / ".claude" / "workflow" / "config.md"
        cfg.parent.mkdir(parents=True)
        cfg.write_text("# Workflow config\n\n## Execution\n\n", encoding="utf-8")
        self.cfg = cfg
        exclude = repo / ".git" / "info" / "exclude"
        exclude.parent.mkdir(exist_ok=True)
        exclude.write_text(".claude/\n.work/\n", encoding="utf-8")
        self.epic = repo / ".claude" / "worktrees" / RUN
        self.epic.parent.mkdir(parents=True)
        git("worktree", "add", "-q", "-b", "epic", self.epic.as_posix(), "main", cwd=repo)
        self.head = git("rev-parse", "main", cwd=repo)
        self.red = git("rev-parse", "epic", cwd=repo)
        self.queue = self.run_dir / "merge-queue"

    def strategy(self, name: str, options: str = "max=4") -> None:
        (self.sdir / f"{name}.md").write_text(
            f"---\nname: {name}\nscript: {name}.sh\ndescription: The {name} strategy.\n"
            f"options: {options}\n---\n\nWhen to use: always.\n", encoding="utf-8")
        (self.sdir / f"{name}.sh").write_text(
            SCRIPT.format(d=self.sdir.as_posix(), name=name), encoding="utf-8", newline="\n")

    def config_line(self, line: str) -> None:
        self.cfg.write_text(f"# Workflow config\n\n## Execution\n\nMerge strategy: {line}\n",
                            encoding="utf-8")

    def run_file(self, text: str) -> None:
        (self.run_dir / "merge-strategy").write_text(text + "\n", encoding="utf-8")

    def mode(self, word: str) -> None:
        (self.sdir / "mode").write_text(word, encoding="utf-8")

    def log(self) -> list[str]:
        p = self.sdir / "log"
        return p.read_text(encoding="utf-8").splitlines() if p.exists() else []

    def env(self) -> dict:
        return {"PAD_STRATEGIES_DIR": self.sdir.as_posix()}

    def queue_empty(self) -> bool:
        return not self.queue.exists() or self.queue.read_text(encoding="utf-8").strip() == ""

    def ready(self, key: str, head: str | None = None, red: str | None = None):
        return self.run_script("merge.sh", "--run", RUN, "--ready", key, head or self.head,
                               red or self.red, cwd=self.repo, env=self.env())

    def status(self) -> list[str]:
        r = self.run_script("merge.sh", "--run", RUN, "--status", cwd=self.repo, env=self.env())
        assert r.returncode == 0, r.stdout + r.stderr
        return r.stdout.splitlines()

    def drain_in_background(self, key: str) -> subprocess.Popen:
        """Start a drain whose first pass blocks in the strategy (`hold`); wait until it holds."""
        (self.sdir / "hold").write_text("", encoding="utf-8")
        full = dict(os.environ)
        full.update(self.env())
        proc = subprocess.Popen(
            [BASH, (BIN / "merge.sh").as_posix(), "--run", RUN, "--ready", key, self.head, self.red],
            cwd=str(self.repo), env=full, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8")
        deadline = time.time() + 90
        while time.time() < deadline and proc.poll() is None and not (self.sdir / "held").exists():
            time.sleep(0.1)
        return proc

    def release(self, proc: subprocess.Popen) -> str:
        (self.sdir / "hold").unlink(missing_ok=True)
        out, _ = proc.communicate(timeout=90)
        return out


@pytest.fixture
def env(repo, tmp_path, run_script):
    return Env(repo, tmp_path, run_script)


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.kill()
        proc.communicate()


@pytest.mark.slow
@pytest.mark.parametrize("which", ["task_head", "red"])
def test_o1_unknown_sha_is_refused_and_the_queue_is_unchanged(env, which):
    env.strategy("fixa")
    env.config_line("fixa")
    env.queue.write_text(f"E0-T0 {env.head} {env.red}\n", encoding="utf-8")
    before = env.queue.read_bytes()
    r = env.ready("E1-T1", head=BAD1 if which == "task_head" else None,
                  red=BAD1 if which == "red" else None)
    assert r.returncode == 2, r.stdout + r.stderr
    assert f"ERROR E1-T1: unknown sha {BAD1}" in r.stdout.splitlines()
    assert env.queue.read_bytes() == before
    assert env.log() == []


@pytest.mark.slow
def test_o1_unknown_sha_with_no_queue_adds_no_entry(env):
    env.strategy("fixa")
    env.config_line("fixa")
    r = env.ready("E1-T1", head=BAD2)
    assert r.returncode == 2, r.stdout + r.stderr
    assert f"ERROR E1-T1: unknown sha {BAD2}" in r.stdout.splitlines()
    assert env.queue_empty()
    assert env.log() == []


@pytest.mark.slow
def test_o2_ready_with_no_drain_drains_the_queue_through_the_strategy(env):
    env.strategy("fixa")
    env.config_line("fixa")
    r = env.ready("E1-T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert env.log() == ["fixa max=4 keys=E1-T1,"]
    assert "REJECTED E1-T1: fixture" in r.stdout.splitlines()
    assert env.queue_empty()


@pytest.mark.slow
def test_o2_drain_pid_file_exists_while_draining_and_is_gone_after(env):
    env.strategy("fixa")
    env.config_line("fixa")
    proc = env.drain_in_background("E1-T1")
    try:
        assert (env.sdir / "held").exists(), "the drain never reached the strategy"
        pid = (env.run_dir / "merge-drain.pid").read_text(encoding="utf-8").strip()
        assert pid.isdigit()
        env.release(proc)
    finally:
        _stop(proc)
    assert not (env.run_dir / "merge-drain.pid").exists(), "pid file left after the drain"


@pytest.mark.slow
def test_o2_ready_during_a_drain_queues_and_the_drain_lands_it_in_a_later_pass(env):
    env.strategy("fixa")
    env.config_line("fixa")
    proc = env.drain_in_background("E1-T1")
    try:
        assert (env.sdir / "held").exists(), "the drain never reached the strategy"
        r = env.ready("E1-T2")
        assert r.returncode == 0, r.stdout + r.stderr
        assert r.stdout.strip().splitlines() == ["QUEUED E1-T2"]
        out = env.release(proc)
    finally:
        _stop(proc)
    assert env.log() == ["fixa max=4 keys=E1-T1,", "fixa max=4 keys=E1-T2,"]
    assert "REJECTED E1-T2: fixture" in out.splitlines()


@pytest.mark.slow
def test_o4_strategy_committing_to_the_epic_without_merge_task_is_an_error(env):
    env.strategy("fixa")
    env.config_line("fixa")
    env.mode("commit")
    r = env.ready("E1-T1")
    assert r.returncode == 2, r.stdout + r.stderr
    assert any(l.startswith("ERROR E1-T1: ") for l in r.stdout.splitlines()), r.stdout


@pytest.mark.slow
def test_o4_ticket_with_no_result_line_is_an_error_for_that_ticket_only(env):
    env.strategy("fixa")
    env.config_line("fixa")
    env.mode("first-only")
    env.queue.write_text(f"E1-T1 {env.head} {env.red}\n", encoding="utf-8")
    r = env.ready("E1-T2")
    lines = r.stdout.splitlines()
    assert r.returncode == 2, r.stdout + r.stderr
    assert any(l.startswith("ERROR E1-T2: ") for l in lines), r.stdout
    assert not any(l.startswith("ERROR E1-T1") for l in lines), r.stdout


@pytest.mark.slow
def test_o4_strategy_answering_every_ticket_without_committing_is_not_an_error(env):
    env.strategy("fixa")
    env.config_line("fixa")
    r = env.ready("E1-T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert not any(l.startswith("ERROR") for l in r.stdout.splitlines())
    assert git("rev-parse", "HEAD", cwd=env.epic) == env.head


@pytest.mark.slow
def test_o16_run_file_beats_the_config_line(env):
    env.strategy("fixa")
    env.strategy("fixb")
    env.config_line("fixa")
    env.run_file("fixb")
    r = env.ready("E1-T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert env.log() == ["fixb max=4 keys=E1-T1,"]


@pytest.mark.slow
def test_o16_config_line_is_used_without_a_run_file_and_its_options_are_parsed(env):
    env.strategy("fixa")
    env.config_line("fixa max=3")
    r = env.ready("E1-T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert env.log() == ["fixa max=3 keys=E1-T1,"]


@pytest.mark.slow
def test_o16_run_file_options_are_parsed(env):
    env.strategy("fixa")
    env.run_file("fixa max=7")
    r = env.ready("E1-T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert env.log() == ["fixa max=7 keys=E1-T1,"]


@pytest.mark.slow
@pytest.mark.parametrize("config", [None, "dynamic"])
def test_o16_dynamic_with_no_run_file_runs_batch(env, config):
    env.strategy("batch")
    env.strategy("fixa")
    if config:
        env.config_line(config)
    r = env.ready("E1-T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert env.log() == ["batch max=4 keys=E1-T1,"]


@pytest.mark.slow
@pytest.mark.parametrize("where,line", [
    ("run", "nosuch"), ("run", "fixa bogus=1"), ("run", "dynamic"),
    ("config", "nosuch"), ("config", "fixa bogus=1"),
])
def test_o16_unknown_name_undeclared_option_or_dynamic_in_run_file_errors_before_merging(
        env, where, line):
    env.strategy("fixa")
    env.strategy("batch")
    if where == "run":
        env.run_file(line)
    else:
        env.config_line(line)
    r = env.ready("E1-T1")
    assert r.returncode != 0, r.stdout + r.stderr
    assert any(l.startswith("ERROR") for l in r.stdout.splitlines()), r.stdout
    assert env.log() == []
    assert git("rev-parse", "HEAD", cwd=env.epic) == env.head


@pytest.mark.slow
def test_o16_run_file_rewritten_during_a_pass_takes_effect_from_the_next_pass(env):
    env.strategy("fixa")
    env.strategy("fixb")
    env.run_file("fixa")
    proc = env.drain_in_background("E1-T1")
    try:
        assert (env.sdir / "held").exists(), "the drain never reached the strategy"
        env.run_file("fixb")
        r = env.ready("E1-T2")
        assert r.stdout.strip().splitlines() == ["QUEUED E1-T2"]
        env.release(proc)
    finally:
        _stop(proc)
    assert env.log() == ["fixa max=4 keys=E1-T1,", "fixb max=4 keys=E1-T2,"]


@pytest.mark.slow
def test_o23_status_before_any_pass_reports_an_empty_idle_run(env):
    env.strategy("fixa")
    env.config_line("fixa")
    assert env.status() == ["QUEUE 0", "DRAIN idle", "LAST none"]


@pytest.mark.slow
def test_o23_status_counts_the_queued_tickets(env):
    env.strategy("fixa")
    env.config_line("fixa")
    env.queue.write_text(f"E1-T1 {env.head} {env.red}\nE1-T2 {env.head} {env.red}\n",
                         encoding="utf-8")
    lines = env.status()
    assert lines[0] == "QUEUE 2"
    assert lines[1] == "DRAIN idle"


@pytest.mark.slow
def test_o23_status_reports_the_last_finished_pass(env):
    env.strategy("fixa")
    env.config_line("fixa")
    env.mode("mixed")
    env.queue.write_text(f"E1-T1 {env.head} {env.red}\nE1-T2 {env.head} {env.red}\n",
                         encoding="utf-8")
    r = env.ready("E1-T3")
    assert r.returncode == 0, r.stdout + r.stderr
    lines = env.status()
    assert lines[:2] == ["QUEUE 0", "DRAIN idle"]
    assert re.fullmatch(r"LAST fixa merged=0 rejected=2 conflict=1 gates=\d+", lines[2]), lines


@pytest.mark.slow
def test_o23_status_during_a_drain_reports_it_running_with_the_waiting_queue(env):
    env.strategy("fixa")
    env.config_line("fixa")
    proc = env.drain_in_background("E1-T1")
    try:
        assert (env.sdir / "held").exists(), "the drain never reached the strategy"
        assert env.ready("E1-T2").stdout.strip() == "QUEUED E1-T2"
        lines = env.status()
        assert lines[:2] == ["QUEUE 1", "DRAIN running"]
        assert lines[2] == "LAST none"
        env.release(proc)
    finally:
        _stop(proc)
