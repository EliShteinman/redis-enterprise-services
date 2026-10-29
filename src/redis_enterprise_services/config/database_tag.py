from pydantic import BaseModel, Field


class DatabaseTag(BaseModel):
    key: str = Field(pattern=r'^[^&<>"]+$')
    value: str
