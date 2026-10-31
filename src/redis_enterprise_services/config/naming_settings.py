from pydantic import BaseModel, Field


class NameRulesSettings(BaseModel):
    pattern: str = Field(min_length=1)
    max_length: int = Field(gt=0)


class NamingSettings(BaseModel):
    database: NameRulesSettings
