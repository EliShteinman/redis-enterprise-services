from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import NonNegativeInt, PositiveInt

from redis_enterprise_services.config.config_model import ConfigModel

type LogLevel = Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]


class LogFormat(StrEnum):
    LINE = "line"
    JSON = "json"


class LogFileSettings(ConfigModel):
    enabled: bool
    format: LogFormat
    path: Path
    max_bytes: PositiveInt
    backup_count: NonNegativeInt
    encoding: str


class LogSettings(ConfigModel):
    level: LogLevel
    line_format: str
    line_format_defaults: dict[str, str]
    date_format: str
    stream: Literal["ext://sys.stdout", "ext://sys.stderr"]
    console_format: LogFormat
    json_dropped_fields: frozenset[str]
    file: LogFileSettings
    root_propagating_loggers: list[str]
    quiet_paths: frozenset[str]
    quiet_kept_level: LogLevel
