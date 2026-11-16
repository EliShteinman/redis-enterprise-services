from typing import Literal

from redis_enterprise_services.config.config_model import ConfigModel


class LogSettings(ConfigModel):
    level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
    line_format: str
    line_format_defaults: dict[str, str]
    date_format: str
    stream: Literal["ext://sys.stdout", "ext://sys.stderr"]
    root_propagating_loggers: list[str]
