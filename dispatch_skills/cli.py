"""Thin launcher for install.sh.

The installer is bash and stays bash — one implementation, shared with the npx entry point.
This module only finds a bash to run it with, forwards argv, and returns its exit code.

    uvx --from git+https://github.com/assafcaf/dispatch-skills dispatch-skills --project
    pipx run --spec git+https://github.com/assafcaf/dispatch-skills dispatch-skills --user
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _payload_root() -> Path:
    """Where install.sh lives.

    Installed as a wheel the payload sits under this package as ``payload/``; run straight
    from a clone it is the repository root, one level up. Checked in that order so a wheel
    never silently uses a stale checkout that happens to be nearby.
    """
    packaged = Path(__file__).resolve().parent / "payload"
    if (packaged / "install.sh").is_file():
        return packaged
    return Path(__file__).resolve().parent.parent


def _find_bash() -> str:
    """On Windows prefer Git Bash.

    A bare ``bash`` there is often WSL's, which runs in a different filesystem namespace and
    would install into the WSL home rather than the one Claude Code reads.
    """
    if sys.platform != "win32":
        return "bash"

    candidates = [
        os.environ.get("GIT_BASH"),
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Git" / "bin" / "bash.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Git" / "bin" / "bash.exe",
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return str(c)

    print(
        "dispatch-skills: could not find Git Bash. Install Git for Windows or set GIT_BASH.\n"
        "Falling back to `bash` on PATH — if that is WSL, this installs into the WSL home.",
        file=sys.stderr,
    )
    return "bash"


def main() -> int:
    script = _payload_root() / "install.sh"
    if not script.is_file():
        print(f"dispatch-skills: install.sh not found at {script}", file=sys.stderr)
        return 1

    try:
        # stdio is inherited, which is what keeps the --wire prompt interactive.
        env = dict(os.environ)
        if sys.platform == "win32":
            # Git Bash rewrites POSIX-looking arguments into Windows paths before the script
            # sees them: `--project /home/me/app` arrives as `C:/Program Files/Git/home/...`.
            env["MSYS_NO_PATHCONV"] = "1"
            env["MSYS2_ARG_CONV_EXCL"] = "*"
        return subprocess.call([_find_bash(), str(script), *sys.argv[1:]], env=env)
    except OSError as exc:
        print(f"dispatch-skills: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
