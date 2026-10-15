"""channel.sh: owners post to and read a run's channel.md in the main checkout."""
from __future__ import annotations

import re
from pathlib import Path

RUN = "E7"
ENTRY = re.compile(r"^- (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) ([^:]+): (.*)$")


def channel(main: Path) -> Path:
    return main / ".work" / "runs" / RUN / "channel.md"


def test_first_post_creates_file_with_header(repo, run_script):
    r = run_script("channel.sh", "post", RUN, "E7-T1", "registry.ts gains `export * from './x'`", cwd=repo)
    assert r.returncode == 0, r.stderr
    text = channel(repo).read_text(encoding="utf-8").splitlines()
    assert text[0] == f"# Channel: {RUN}"
    m = ENTRY.match(text[-1])
    assert m, text
    assert m.group(2) == "E7-T1"
    assert m.group(3) == "registry.ts gains `export * from './x'`"


def test_post_from_linked_worktree_lands_in_main(repo, worktree, run_script):
    wt = worktree(repo, "E7-T2")
    r = run_script("channel.sh", "post", RUN, "E7-T2", "-e not an option \\n", cwd=wt)
    assert r.returncode == 0, r.stderr
    assert not (wt / ".work").exists()
    last = channel(repo).read_text(encoding="utf-8").splitlines()[-1]
    assert last.endswith("E7-T2: -e not an option \\n")


def test_posts_append_never_rewrite(repo, run_script):
    run_script("channel.sh", "post", RUN, "A", "one", cwd=repo)
    run_script("channel.sh", "post", RUN, "B", "two", cwd=repo)
    text = channel(repo).read_text(encoding="utf-8").splitlines()
    assert text.count(f"# Channel: {RUN}") == 1
    assert [ENTRY.match(l).group(3) for l in text if l.startswith("- ")] == ["one", "two"]


def test_read_all_and_since(repo, run_script):
    f = channel(repo)
    f.parent.mkdir(parents=True)
    f.write_text(
        f"# Channel: {RUN}\n\n"
        "- 2026-10-15T10:00:00Z A: early\n"
        "- 2026-10-15T11:00:00Z B: middle\n"
        "- 2026-10-15T12:00:00Z C: late\n",
        encoding="utf-8",
    )
    r = run_script("channel.sh", "read", RUN, cwd=repo)
    assert r.returncode == 0, r.stderr
    assert [l.split(": ", 1)[1] for l in r.stdout.splitlines()] == ["early", "middle", "late"]
    r = run_script("channel.sh", "read", RUN, "--since", "2026-10-15T11:00:00Z", cwd=repo)
    assert r.stdout.splitlines() == ["- 2026-10-15T12:00:00Z C: late"]


def test_read_missing_channel_is_empty(repo, run_script):
    r = run_script("channel.sh", "read", "nothing-yet", cwd=repo)
    assert r.returncode == 0
    assert r.stdout == ""


def test_multiline_post_stays_one_entry(repo, run_script):
    run_script("channel.sh", "post", RUN, "A", "line one\nline two", cwd=repo)
    entries = [l for l in channel(repo).read_text(encoding="utf-8").splitlines() if l.startswith("- ")]
    assert len(entries) == 1
    assert entries[0].endswith("A: line one line two")


def test_usage_and_outside_git(repo, tmp_path, run_script):
    for args in [(), ("post", RUN, "A"), ("read",), ("bogus", RUN), ("read", RUN, "--since")]:
        assert run_script("channel.sh", *args, cwd=repo).returncode == 64, args
    outside = tmp_path / "nogit"
    outside.mkdir()
    assert run_script("channel.sh", "post", RUN, "A", "x", cwd=outside).returncode == 1
