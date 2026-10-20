"""The suite's own guards, registered by tests/conftest.py: a fast-tier budget, a leaked-process
sweep at session end, and a helper that starts payload scripts in the background and stops their
whole process trees. Lives outside tests/ so the red freeze on test files does not cover it."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD = ROOT / "payload"
BIN = PAYLOAD / "claude" / "workflow" / "bin"


def _find_bash() -> str:
    override = os.environ.get("PAD_BASH")
    if override:
        return override
    if os.name == "nt":
        exe = shutil.which("git")
        if exe:
            for parent in Path(exe).resolve().parents:
                candidate = parent / "bin" / "bash.exe"
                if candidate.is_file():
                    return str(candidate)
    return shutil.which("bash") or "bash"


BASH = _find_bash()


# --- processes: listing, tree kill, background scripts ----------------------------------------

def real_bash() -> str:
    """The bash that really runs a script. On Windows, Git's bin/bash.exe is a launcher: killing
    it leaves the usr/bin/bash.exe it started running, so tests that start a script in the
    background start usr/bin/bash.exe and stop it by tree."""
    real = Path(BASH).parent.parent / "usr" / "bin" / "bash.exe"
    return str(real) if os.name == "nt" and real.is_file() else BASH


# Prints `pid ppid command` for every process the bash can see (builtins only where /proc exists).
_LISTER = r"""
if [ -r /proc/self/stat ]; then
  for d in /proc/[0-9]*; do
    p=${d#/proc/}
    read -r line < "$d/stat" 2>/dev/null || continue
    rest=${line##*) }; set -- $rest
    mapfile -d '' -t a < "$d/cmdline" 2>/dev/null
    printf '%s %s %s\n' "$p" "${2:-0}" "${a[*]}"
  done
else
  ps -eo pid=,ppid=,args=
fi
"""


def _bash_run(script: str, *args: str, timeout: float = 120) -> str:
    r = subprocess.run([real_bash(), "-c", script, "_", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout, check=False)
    return r.stdout


def _processes() -> list[tuple[int, int, str]]:
    out = []
    for line in _bash_run(_LISTER).splitlines():
        parts = line.split(" ", 2)
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            out.append((int(parts[0]), int(parts[1]), parts[2] if len(parts) > 2 else ""))
    return out


def _tree(roots, procs) -> set[int]:
    kids: dict[int, list[int]] = {}
    for pid, ppid, _ in procs:
        kids.setdefault(ppid, []).append(pid)
    seen, todo = set(), list(roots)
    while todo:
        p = todo.pop()
        if p in seen:
            continue
        seen.add(p)
        todo.extend(kids.get(p, ()))
    return seen


def _kill_pids(pids) -> None:
    pids = sorted(int(p) for p in pids)
    if pids:
        _bash_run('kill -9 "$@" 2>/dev/null; true', *map(str, pids))


def kill_tree(pid: int) -> None:
    """Kill `pid` (as bash numbers it) and every process below it."""
    _kill_pids(_tree([pid], _processes()))


def kill_naming(path) -> None:
    """Kill every process whose command line names `path` (a test's tmp dir), and its tree: what a
    test started through Git's launcher leaves behind when it kills only the launcher."""
    procs = _processes()
    needles = _forms(path)
    roots = [p for p, _pp, c in procs
             if not _is_test_runner(c) and any(n in c.replace("\\", "/").lower() for n in needles)]
    _kill_pids(_tree(roots, procs))


def _forms(path) -> set[str]:
    """The spellings a command line may use for a path, lower-cased with forward slashes."""
    p = str(path).replace("\\", "/").rstrip("/").lower()
    forms = {p}
    if len(p) > 2 and p[1] == ":":
        forms.add("/" + p[0] + p[2:])
    return forms


class _Background:
    """Handle on a script started by `bg.start`."""

    def __init__(self, popen: subprocess.Popen, pidfile: Path):
        self.popen = popen
        self._pidfile = pidfile

    @property
    def pid(self) -> int:
        """The script's own bash pid, as bash numbers it."""
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            text = self._pidfile.read_text().strip() if self._pidfile.exists() else ""
            if text.isdigit():
                return int(text)
            time.sleep(0.02)
        raise RuntimeError("the background script never recorded its pid")


class _Bg:
    def __init__(self):
        self._started: list[_Background] = []

    def start(self, name: str, *args: str, cwd, env: dict | None = None) -> _Background:
        full_env = dict(os.environ)
        if env:
            full_env.update(env)
        full_env["PAD_BG_ID"] = ident = uuid.uuid4().hex  # what stop_all sweeps by
        fd, pidfile = tempfile.mkstemp(prefix="pad-bg-", suffix=".pid")
        os.close(fd)
        pidfile = Path(pidfile)
        script = (BIN / name).as_posix()
        popen = subprocess.Popen(
            [real_bash(), "-c", 'echo $$ > "$1"; shift; exec "$BASH" "$@"', "_",
             pidfile.as_posix(), script, *args],
            cwd=str(cwd), env=full_env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        handle = _Background(popen, pidfile)
        handle.ident = ident
        self._started.append(handle)
        return handle

    def stop_all(self) -> None:
        roots = []
        for h in self._started:
            text = h._pidfile.read_text().strip() if h._pidfile.exists() else ""
            if text.isdigit():
                roots.append(int(text))
        if roots:
            _kill_pids(_tree(roots, _processes()))
        # a script killed mid-start may have spawned a child after the tree was read: whatever
        # inherited this start's id is its descendant, however it was reparented
        late = set()
        for h in self._started:
            late |= _marked_pids("PAD_BG_ID", h.ident)
        if late:
            _kill_pids(late)
        for h in self._started:
            if h.popen.poll() is None:
                h.popen.kill()
            try:
                h.popen.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
            try:
                h._pidfile.unlink()
            except OSError:
                pass
        self._started.clear()


@pytest.fixture
def bg():
    """Starts payload scripts in the background and stops their whole process trees at teardown.

    `bg.start(name, *args, cwd, env=None)` runs `payload/.../bin/<name>` under the real bash (not
    Git's launcher) and returns an object with `.pid`, the script's own bash pid. Teardown, on
    pass, fail or timeout, kills every process started through it, descendants included.
    """
    starter = _Bg()
    try:
        yield starter
    finally:
        starter.stop_all()


# --- the suite guards itself: a fast-test budget and a leaked-process sweep --------------------

def pytest_addoption(parser):
    parser.addini("fast_test_budget",
                  "seconds the call phase of a test not marked slow may take", default="")


# Tests running right now in this process (setup to teardown). A session that ends while this is
# above 0 was started by a test, in this process.
_running = 0
# A session in a process a test started (pytester's subprocess runs) knows it from its environment.
_started_by_a_test = "PYTEST_CURRENT_TEST" in os.environ

# Every process a test starts inherits this variable from the session, so the session-end check
# finds them by it, not by what their command lines say. An xdist worker keeps the controller's
# value; a session a test started gets its own, so it never sweeps its parent's processes.
_MARK_VAR = "PAD_TEST_SESSION"
if _started_by_a_test or not os.environ.get(_MARK_VAR):
    os.environ[_MARK_VAR] = uuid.uuid4().hex
_MARK = os.environ[_MARK_VAR]


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    global _running
    outcome = yield
    if call.when == "setup":
        _running += 1
    elif call.when == "teardown":
        _running -= 1
    if call.when != "call":
        return
    try:
        budget = float(item.config.getini("fast_test_budget") or 0)
    except ValueError:
        return
    report = outcome.get_result()
    if budget <= 0 or report.outcome != "passed" or item.get_closest_marker("slow"):
        return
    took = call.stop - call.start
    if took > budget:
        report.outcome = "failed"
        report.longrepr = f"FAST BUDGET {item.nodeid} {took:.1f}s: mark it slow or make it fast"



def _is_test_runner(command: str) -> bool:
    argv0 = command.split(" ", 1)[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
    return argv0.startswith(("python", "py.", "pytest")) or argv0 == "py"


# Prints the pid of every process whose environment carries `$1` (a NAME=value line), listing
# bash and its own children excepted. Needs /proc/<pid>/environ; prints nothing where it is absent.
_MARKED = r"""
M="$1"
for d in /proc/[0-9]*; do
  p=${d#/proc/}
  [ "$p" = "$$" ] && continue
  while IFS= read -r -d '' kv; do
    if [ "$kv" = "$M" ]; then echo "$p"; break; fi
  done < "$d/environ" 2>/dev/null
done
"""


def _marked_pids(var: str | None = None, value: str | None = None) -> set[int]:
    out = _bash_run(_MARKED, f"{var or _MARK_VAR}={value or _MARK}")
    return {int(x) for x in out.split() if x.isdigit()}


def _leaks(config) -> list[tuple[int, str, str]]:
    """Processes still alive that inherited this session's marker (so a test started them, however
    their command line reads): (pid, command, the test dir that started it, when it names one).
    Kills them and their trees."""
    procs = _processes()
    me = os.getpid()
    by_pid = {pid: command for pid, _ppid, command in procs}
    marked = {p for p in _marked_pids() if p in by_pid}
    if os.name != "nt" and not Path("/proc").is_dir():  # no environ to read: use descent instead
        marked = _tree([me], procs) - {me}
    named = {p: by_pid[p] for p in marked if p != me and not _is_test_runner(by_pid[p])}
    root = None
    try:
        root = config._tmp_path_factory.getbasetemp()
    except Exception:
        pass
    # report the tops of the trees: a listing child or a sleeping grandchild is part of its parent
    tops = {p for p in named if not any(q != p and p in _tree([q], procs) for q in named)}
    found = []
    for pid in sorted(tops):
        command = named[pid]
        test = ""
        if root is not None:
            for form in _forms(root):
                m = re.search(re.escape(form) + r"/([^/\s]+)", command.replace("\\", "/").lower())
                if m:
                    test = m.group(1)
                    break
        found.append((pid, command, test))
    if named:
        _kill_pids(_tree(list(named), procs))
    return found


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    if hasattr(config, "workerinput"):  # an xdist worker: the controller sweeps once all are done
        return
    if _running > 0:  # started by a test in this process: it owns nothing the outer session runs
        return
    leaks = _leaks(config)
    if not leaks:
        return
    reporter = config.pluginmanager.get_plugin("terminalreporter")
    for pid, command, test in leaks:
        line = f"LEAK {pid} {' '.join(command.split())[:300]}"
        if test:
            line += f"  [started by a test using {test}]"
        if reporter is not None:
            reporter.write_line(line)
        else:
            print(line)
    session.exitstatus = pytest.ExitCode.TESTS_FAILED
