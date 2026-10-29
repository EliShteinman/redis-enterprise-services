from pydantic import BaseModel, Field, JsonValue


class DefaultsOverride(BaseModel):
    when: dict[str, str] = Field(min_length=1)
    values: dict[str, JsonValue] = Field(min_length=1)


class DatabaseDefaultsSettings(BaseModel):
    values: dict[str, JsonValue]
    overrides: list[DefaultsOverride]
