"""Shared set-up for the pad-test.sh tests: a repo with a `## Test regime` config, the fake
runner adapter installed as the repo's own (`.claude/pad-plugins/runners/fake.sh`), a state dir
the fake plays results from, and an environment that makes the run quick and hermetic."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from conftest import BASH, BIN, git  # noqa: E402

PAD_TEST = (BIN / "pad-test.sh").as_posix()
LIMITS = (BIN / "pad-test-limits.sh").as_posix()
RUN = "E9"

CONFIG = """\
# Workflow config

## Test regime

Runner: fake
Repeat limit: {repeat}
Ticket run limit: {runs}

| Tier | Adapter selector | Per-test kill | Budget | Declared GB | Workers |
|---|---|---|---|---|---|
| fast | tests/fast | 60 | 120 | 0.5 | 2 |
| heavy | tests/heavy | 300 | 600 | 2 | 1 |
| epic | tests/epic | 900 | 1800 | 4 | 1 |
"""


class Harness:
    def __init__(self, repo: Path, tmp: Path, repeat: str = "3", runs: str = "12"):
        self.repo = repo
        self.state = tmp / "fake-state"
        self.state.mkdir()
        self.log = tmp / "fake.log"
        self.log.write_text("", encoding="utf-8")
        self.n = 0
        runners = repo / ".claude" / "pad-plugins" / "runners"
        runners.mkdir(parents=True)
        (runners / "fake.sh").write_bytes((HERE / "fake.sh").read_bytes())
        wf = repo / ".claude" / "workflow"
        wf.mkdir(parents=True, exist_ok=True)
        (wf / "config.md").write_text(CONFIG.format(repeat=repeat, runs=runs), encoding="utf-8", newline="\n")
        (repo / ".gitignore").write_text(".work/\n", encoding="utf-8")
        (repo / "tests" / "fast").mkdir(parents=True)
        (repo / "tests" / "fast" / "test_a.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
        git("add", "-A", cwd=repo)
        git("commit", "-q", "-m", "regime", cwd=repo)

    def results(self, n: int, *lines: str, exit_code: int | None = None) -> None:
        (self.state / f"results.{n}").write_text("".join(f"{x}\n" for x in lines), encoding="utf-8", newline="\n")
        if exit_code is not None:
            (self.state / f"exit.{n}").write_text(f"{exit_code}\n", encoding="utf-8")

    def env(self, **extra: str) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("PAD_MEMORY", "PAD_HOST", "PAD_SUITE", "PAD_CAP", "PAD_CORES", "PAD_CONTAIN"))}
        env.update(PAD_MEMORY_PROBE="echo 1", PAD_MEMORY_TOTAL_GB="16", PAD_CONTAIN="group",
                   PAD_SAMPLE_INTERVAL="1", FAKE_STATE=self.state.as_posix(), FAKE_LOG=self.log.as_posix())
        env.update(extra)
        return env

    def change_tree(self) -> None:
        """Edit a tracked file: a new working-tree hash on the same commit."""
        self.n += 1
        (self.repo / "README.md").write_text(f"fixture repo {self.n}\n", encoding="utf-8")

    def run(self, *args: str, role: str = "owner", ticket: str = "E9-T1", run: str = RUN,
            env: dict[str, str] | None = None, timeout: float = 180):
        return subprocess.run(
            [BASH, PAD_TEST, "--run", run, "--ticket", ticket, "--role", role, *args],
            cwd=str(self.repo), env=env or self.env(), capture_output=True, text=True,
            encoding="utf-8", timeout=timeout)

    def verbs(self) -> list[str]:
        return [x.split(" ", 1)[0] for x in self.log.read_text(encoding="utf-8").splitlines() if x.strip()]

    def calls(self, verb: str) -> list[str]:
        return [x for x in self.log.read_text(encoding="utf-8").splitlines() if x.startswith(verb + " ")]

    def gates(self, run: str = RUN) -> list[dict]:
        f = self.repo / ".work" / "runs" / run / "gates.jsonl"
        if not f.is_file():
            return []
        return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]


def out(r) -> str:
    return r.stdout + r.stderr
