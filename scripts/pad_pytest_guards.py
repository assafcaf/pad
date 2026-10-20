"""The suite's own guards: fast-tier budget, leak sweep, background-script helper (stubs)."""
import pytest


def pytest_addoption(parser):
    pass


def pytest_runtest_makereport(item, call):
    pass


def pytest_sessionfinish(session, exitstatus):
    pass


@pytest.fixture
def bg():
    raise NotImplementedError("bg")


def kill_tree(pid: int) -> None:
    raise NotImplementedError("kill_tree")


def kill_naming(path) -> None:
    raise NotImplementedError("kill_naming")


def real_bash() -> str:
    raise NotImplementedError("real_bash")
