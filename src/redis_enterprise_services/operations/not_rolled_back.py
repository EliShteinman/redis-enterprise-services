from pydantic import BaseModel


class NotRolledBack(BaseModel):
    cluster: str
    type: str
    name: str
    uid: int | None
    error: str | None
