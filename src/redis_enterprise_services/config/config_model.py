from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class ConfigModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
