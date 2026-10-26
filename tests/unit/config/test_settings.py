from pathlib import Path

import pytest

from redis_enterprise_services.config import Settings

CONFIG_FILE: str = (
    'log:\n  level: INFO\n  stream: stdout\n  line_pattern: "%(message)s"\n  date_format: "%H:%M"\n'
)


@pytest.fixture
def config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "settings.yaml").write_text(data=CONFIG_FILE, encoding="utf-8")


def test_values_come_from_the_file(config_file: None) -> None:
    assert Settings().log.line_pattern == "%(message)s"


def test_environment_overrides_the_file(config_file: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(name="RES_LOG__LEVEL", value="ERROR")

    assert Settings().log.level == "ERROR"
