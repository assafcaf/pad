"""statusline.py shows the address other sessions message this one by.

`SendMessage` and `ListAgents` route a session by its name (`pad-0d`), which Claude Code keeps
in `<config dir>/sessions/<pid>.json` beside the `sessionId` the status line is given. The raw
id is not an address, so it is only the fallback when the registry has no row for the session.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import PAYLOAD

SCRIPT = PAYLOAD / "claude" / "statusline.py"
SESSION = "ed5027c4-faa4-46a3-a2f5-8e352e735269"


def register(config: Path, pid: int, session: str, name: str) -> None:
    sessions = config / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    row = {"pid": pid, "sessionId": session, "name": name, "kind": "interactive"}
    (sessions / f"{pid}.json").write_text(json.dumps(row), encoding="utf-8")


def segments(tmp_path: Path, payload: dict) -> list[str]:
    config = tmp_path / "config"
    config.mkdir(exist_ok=True)
    env = dict(os.environ)
    env["CLAUDE_CONFIG_DIR"] = str(config)
    env["TEMP"] = env["TMP"] = env["TMPDIR"] = str(tmp_path)
    payload = {
        "model": {"display_name": "Opus"},
        "workspace": {"current_dir": str(tmp_path), "project_dir": str(tmp_path)},
        **payload,
    }
    out = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=30,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout.strip().split(" | ")


def test_the_session_name_from_the_registry_follows_the_model(tmp_path):
    register(tmp_path / "config", 13796, SESSION, "pad-0d")
    register(tmp_path / "config", 3564, "a1cec94b-2ddc-4057-86ea-decd049a2e18", "pad-d7")
    assert segments(tmp_path, {"session_id": SESSION})[:2] == ["Opus", "@pad-0d"]


def test_a_session_missing_from_the_registry_shows_its_short_id(tmp_path):
    register(tmp_path / "config", 3564, "a1cec94b-2ddc-4057-86ea-decd049a2e18", "pad-d7")
    assert segments(tmp_path, {"session_id": SESSION})[1] == "@ed5027c4"


def test_an_unreadable_registry_row_is_skipped(tmp_path):
    sessions = tmp_path / "config" / "sessions"
    sessions.mkdir(parents=True)
    (sessions / "1.json").write_text("{not json", encoding="utf-8")
    register(tmp_path / "config", 2, SESSION, "pad-0d")
    assert segments(tmp_path, {"session_id": SESSION})[1] == "@pad-0d"


def test_no_session_id_shows_no_address(tmp_path):
    assert not any(part.startswith("@") for part in segments(tmp_path, {}))
