from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class NameViolation(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    rule: str
    message: str

    def describe(self) -> str:
        return f"{self.rule}: {self.message}"
