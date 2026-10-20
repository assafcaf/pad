"""O33: flaky.sh keeps the flaky quarantine: 8 tests, 7 days, 48 h to acknowledge, 100 consecutive
passes to re-admit. A quarantined test runs but does not gate.

    flaky.sh --state <file> --now <epoch seconds> record <id>      QUARANTINED <id>
    flaky.sh --state <file> --now <epoch seconds> ack <id>
    flaky.sh --state <file> --now <epoch seconds> pass <id> [<n>]  n consecutive passes (default 1);
                                                                   READMITTED <id> at 100 in a row
    flaky.sh --state <file> --now <epoch seconds> fail <id>        resets the pass count
    flaky.sh --state <file> --now <epoch seconds> gate <results>   exit 1 on a failure or error of
                                                                   a test that is not quarantined
    flaky.sh --state <file> --now <epoch seconds> check            one `SUITE-OWNER TASK <kind> <id>`
                                                                   line per over-cap, expired and
                                                                   unacknowledged entry
Kinds: quarantine-full (the ninth entry on), quarantine-expired, quarantine-unacknowledged.
No test starts a runner: every verb works on the state file alone.
"""
from __future__ import annotations

from pathlib import Path

T0 = 1_800_000_000
HOUR = 3600
DAY = 24 * HOUR


def _flaky(run_script, tmp_path: Path, now: int, *args: str):
    return run_script(
        "flaky.sh", "--state", (tmp_path / "flaky.state").as_posix(), "--now", str(now), *args,
        cwd=tmp_path,
    )


def _tasks(r) -> list[str]:
    return sorted(line.strip() for line in r.stdout.splitlines() if line.startswith("SUITE-OWNER TASK"))


def _id(n: int) -> str:
    return f"tests/test_f.py::test_{n}"


def _results(tmp_path: Path, text: str) -> str:
    p = tmp_path / "results.txt"
    p.write_text(text, encoding="utf-8")
    return p.as_posix()


def test_o33_recording_a_flaky_test_quarantines_it(tmp_path, run_script):
    r = _flaky(run_script, tmp_path, T0, "record", _id(1))
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"QUARANTINED {_id(1)}" in r.stdout


def test_o33_a_quarantined_failure_does_not_gate(tmp_path, run_script):
    _flaky(run_script, tmp_path, T0, "record", _id(1))
    res = _results(tmp_path, f"failure {_id(1)} boom\nerror {_id(1)} boom\npass tests/test_g.py::test_ok\n")
    r = _flaky(run_script, tmp_path, T0 + HOUR, "gate", res)
    assert r.returncode == 0, r.stdout + r.stderr


def test_o33_a_failure_that_is_not_quarantined_gates_and_is_named(tmp_path, run_script):
    _flaky(run_script, tmp_path, T0, "record", _id(1))
    res = _results(tmp_path, f"failure {_id(1)} boom\nfailure {_id(2)} real break\n")
    r = _flaky(run_script, tmp_path, T0 + HOUR, "gate", res)
    assert r.returncode == 1, r.stdout + r.stderr
    assert _id(2) in r.stdout


def test_o33_an_error_that_is_not_quarantined_gates(tmp_path, run_script):
    res = _results(tmp_path, f"error {_id(3)} import failed\n")
    r = _flaky(run_script, tmp_path, T0, "gate", res)
    assert r.returncode == 1, r.stdout + r.stderr


def test_o33_all_passing_results_pass_the_gate(tmp_path, run_script):
    res = _results(tmp_path, f"pass {_id(3)}\nskipped {_id(4)}\n")
    r = _flaky(run_script, tmp_path, T0, "gate", res)
    assert r.returncode == 0, r.stdout + r.stderr


def test_o33_eight_entries_are_within_the_cap(tmp_path, run_script):
    for n in range(1, 9):
        _flaky(run_script, tmp_path, T0, "record", _id(n))
        _flaky(run_script, tmp_path, T0, "ack", _id(n))
    r = _flaky(run_script, tmp_path, T0 + HOUR, "check")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _tasks(r) == []
    # a quarantine of eight is real: its failures do not gate
    res = _results(tmp_path, f"failure {_id(8)} boom\n")
    assert _flaky(run_script, tmp_path, T0 + HOUR, "gate", res).returncode == 0


def test_o33_the_ninth_entry_is_reported_as_a_suite_owner_task(tmp_path, run_script):
    for n in range(1, 10):
        _flaky(run_script, tmp_path, T0, "record", _id(n))
        _flaky(run_script, tmp_path, T0, "ack", _id(n))
    r = _flaky(run_script, tmp_path, T0 + HOUR, "check")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _tasks(r) == [f"SUITE-OWNER TASK quarantine-full {_id(9)}"]


def test_o33_recording_the_same_test_twice_is_one_entry(tmp_path, run_script):
    for _ in range(9):
        _flaky(run_script, tmp_path, T0, "record", _id(1))
    _flaky(run_script, tmp_path, T0, "ack", _id(1))
    r = _flaky(run_script, tmp_path, T0 + HOUR, "check")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _tasks(r) == []


def test_o33_an_entry_older_than_seven_days_is_reported_expired(tmp_path, run_script):
    _flaky(run_script, tmp_path, T0, "record", _id(1))
    _flaky(run_script, tmp_path, T0, "ack", _id(1))
    r = _flaky(run_script, tmp_path, T0 + 7 * DAY + 1, "check")
    assert _tasks(r) == [f"SUITE-OWNER TASK quarantine-expired {_id(1)}"]


def test_o33_an_entry_just_under_seven_days_is_not_expired(tmp_path, run_script):
    _flaky(run_script, tmp_path, T0, "record", _id(1))
    _flaky(run_script, tmp_path, T0, "ack", _id(1))
    r = _flaky(run_script, tmp_path, T0 + 7 * DAY - 1, "check")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _tasks(r) == []


def test_o33_an_entry_unacknowledged_after_48_hours_is_reported(tmp_path, run_script):
    _flaky(run_script, tmp_path, T0, "record", _id(1))
    r = _flaky(run_script, tmp_path, T0 + 48 * HOUR + 1, "check")
    assert _tasks(r) == [f"SUITE-OWNER TASK quarantine-unacknowledged {_id(1)}"]


def test_o33_an_entry_unacknowledged_under_48_hours_is_not_reported(tmp_path, run_script):
    _flaky(run_script, tmp_path, T0, "record", _id(1))
    r = _flaky(run_script, tmp_path, T0 + 48 * HOUR - 1, "check")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _tasks(r) == []


def test_o33_an_acknowledged_entry_is_not_reported_after_48_hours(tmp_path, run_script):
    _flaky(run_script, tmp_path, T0, "record", _id(1))
    _flaky(run_script, tmp_path, T0 + HOUR, "ack", _id(1))
    r = _flaky(run_script, tmp_path, T0 + 3 * DAY, "check")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _tasks(r) == []


def test_o33_one_hundred_consecutive_passes_readmit_the_test(tmp_path, run_script):
    _flaky(run_script, tmp_path, T0, "record", _id(1))
    r = _flaky(run_script, tmp_path, T0 + HOUR, "pass", _id(1), "99")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "READMITTED" not in r.stdout
    r = _flaky(run_script, tmp_path, T0 + 2 * HOUR, "pass", _id(1))
    assert f"READMITTED {_id(1)}" in r.stdout
    res = _results(tmp_path, f"failure {_id(1)} boom\n")
    assert _flaky(run_script, tmp_path, T0 + 3 * HOUR, "gate", res).returncode == 1


def test_o33_a_failure_resets_the_count_of_consecutive_passes(tmp_path, run_script):
    _flaky(run_script, tmp_path, T0, "record", _id(1))
    _flaky(run_script, tmp_path, T0 + HOUR, "pass", _id(1), "99")
    _flaky(run_script, tmp_path, T0 + HOUR, "fail", _id(1))
    r = _flaky(run_script, tmp_path, T0 + 2 * HOUR, "pass", _id(1), "99")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "READMITTED" not in r.stdout
    res = _results(tmp_path, f"failure {_id(1)} boom\n")
    assert _flaky(run_script, tmp_path, T0 + 3 * HOUR, "gate", res).returncode == 0
