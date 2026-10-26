import traceback
from pathlib import Path

import pytest

from redis_enterprise_services.config import LoggingSettings, Settings, load_settings
from redis_enterprise_services.exceptions import ConfigurationError

VALID_FILE: str = (
    'log:\n  level: INFO\n  stream: stdout\n  line_pattern: "%(message)s"\n  date_format: "%H:%M"\n'
)
REJECTED_VALUE: str = "rejected-value-7f3a"


@pytest.fixture
def config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    path: Path = tmp_path / "config" / "settings.yaml"
    path.parent.mkdir()
    path.write_text(data=VALID_FILE, encoding="utf-8")
    return path


def test_values_come_from_the_file(config_file: Path) -> None:
    assert load_settings().log.line_pattern == "%(message)s"


def test_environment_overrides_the_file(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(name="RES_LOG__LEVEL", value="ERROR")

    assert load_settings().log.level == "ERROR"


def test_invalid_value_is_reported_by_field(config_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(name="RES_LOG__LEVEL", value=REJECTED_VALUE)

    with pytest.raises(ConfigurationError, match=r"log\.level"):
        load_settings()


def test_invalid_value_is_left_out_of_the_traceback(
    config_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(name="RES_LOG__LEVEL", value=REJECTED_VALUE)

    with pytest.raises(ConfigurationError) as raised:
        load_settings()

    assert REJECTED_VALUE not in "".join(traceback.format_exception(raised.value))


def test_broken_yaml_is_reported(config_file: Path) -> None:
    config_file.write_text(data="log: [unclosed", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_settings()


def test_constructor_arguments_override_the_file(config_file: Path) -> None:
    log: LoggingSettings = LoggingSettings(
        level="DEBUG", stream="stdout", line_pattern="%(message)s", date_format="%H"
    )

    assert Settings(log=log).log.level == "DEBUG"
