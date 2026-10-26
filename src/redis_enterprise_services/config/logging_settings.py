from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict


class LoggingSettings(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    level: Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]
    stream: Literal["stdout", "stderr"]
    line_pattern: str
    date_format: str
