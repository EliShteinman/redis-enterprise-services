from pydantic import BaseModel


class NamedResource(BaseModel):
    uid: int
    name: str


class CreatedResource(NamedResource):
    action_uid: str | None
