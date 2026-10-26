from pydantic import JsonValue

from redis_enterprise_services.config import LoggingSettings
from redis_enterprise_services.logger.configuration import logging_config

SETTINGS: LoggingSettings = LoggingSettings(
    level="WARNING", stream="stderr", line_pattern="%(levelname)s %(message)s", date_format="%H:%M"
)
CONFIG: dict[str, JsonValue] = logging_config(settings=SETTINGS)


def test_root_level_comes_from_settings() -> None:
    assert CONFIG["root"]["level"] == "WARNING"


def test_line_format_comes_from_settings() -> None:
    assert CONFIG["formatters"]["line"] == {"format": "%(levelname)s %(message)s", "datefmt": "%H:%M"}


def test_stream_comes_from_settings() -> None:
    assert CONFIG["handlers"]["console"]["stream"] == "ext://sys.stderr"


def test_existing_loggers_stay_enabled() -> None:
    assert CONFIG["disable_existing_loggers"] is False
