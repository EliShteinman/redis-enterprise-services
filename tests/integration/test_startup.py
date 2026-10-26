import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from redis_enterprise_services.__main__ import main

PROJECT_ROOT: Path = Path(__file__).parents[2]


@pytest.fixture
def root_logger_restored() -> Iterator[None]:
    root: logging.Logger = logging.getLogger()
    handlers: list[logging.Handler] = list(root.handlers)
    level: int = root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level=level)


@pytest.fixture
def in_project_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(PROJECT_ROOT)


def test_startup_logs_with_the_project_config(
    root_logger_restored: None, in_project_root: None, capsys: pytest.CaptureFixture[str]
) -> None:
    main()

    assert "| INFO     | redis_enterprise_services.__main__ | redis-enterprise-services started" in (
        capsys.readouterr().out
    )
