from pydantic import BaseModel


class NamedSpec(BaseModel):
    name: str
