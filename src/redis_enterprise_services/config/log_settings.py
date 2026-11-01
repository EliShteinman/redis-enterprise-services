from typing import Literal

from pydantic import BaseModel


class LoggingSettings(BaseModel):
    level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
    line_pattern: str
    date_format: str
    stream: Literal["ext://sys.stdout", "ext://sys.stderr"]
    server_loggers: list[str]
