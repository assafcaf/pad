"""O29: verify-red.sh --expect-text grades the red: the run must fail the stated way and say so.

    verify-red.sh --expect-text '<text>' <commit> -- <test command...>

RED OK needs the expected red exit code AND the text in the run's output; the same exit code
without the text (a failure for another reason) is NOT RED.
"""
from __future__ import annotations

from conftest import git


def _verify(run_script, repo, text: str, shell: str):
    sha = git("rev-parse", "HEAD", cwd=repo)
    return run_script(
        "verify-red.sh", "--expect-text", text, sha, "--", "bash", "-c", shell, cwd=repo
    )


def test_o29_expected_exit_and_text_in_the_output_is_red_ok(repo, run_script):
    r = _verify(run_script, repo, "prefilled name", 'echo "AssertionError: prefilled name missing"; exit 1')
    assert r.returncode == 0, r.stdout + r.stderr
    assert "RED OK" in r.stdout


def test_o29_expected_exit_without_the_text_is_not_red(repo, run_script):
    r = _verify(run_script, repo, "prefilled name", 'echo "AssertionError: something else"; exit 1')
    assert r.returncode == 1, r.stdout + r.stderr
    assert "NOT RED" in r.stdout
    assert "prefilled name" in r.stdout


def test_o29_the_text_with_a_passing_run_is_not_red(repo, run_script):
    r = _verify(run_script, repo, "prefilled name", 'echo "prefilled name"; exit 0')
    assert r.returncode == 1, r.stdout + r.stderr
    assert "NOT RED" in r.stdout


def test_o29_the_text_with_a_collection_error_exit_is_not_red(repo, run_script):
    r = _verify(run_script, repo, "prefilled name", 'echo "ImportError: prefilled name"; exit 2')
    assert r.returncode == 1, r.stdout + r.stderr
    assert "NOT RED" in r.stdout
