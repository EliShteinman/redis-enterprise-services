from typing import Literal

from pydantic import BaseModel


class LoggingSettings(BaseModel):
    level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
    line_pattern: str
    date_format: str
    stream: str
    server_loggers: list[str]
