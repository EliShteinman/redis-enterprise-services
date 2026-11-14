from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class NameViolation(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    rule_id: str
    message: str

    def describe(self) -> str:
        return f"{self.rule_id}: {self.message}"
