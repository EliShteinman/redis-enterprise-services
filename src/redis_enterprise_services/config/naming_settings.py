import re

from pydantic import BaseModel, Field


class NameRulesSettings(BaseModel):
    pattern: re.Pattern[str]
    max_length: int = Field(gt=0)


class NamingSettings(BaseModel):
    database: NameRulesSettings
