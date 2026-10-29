from pydantic import BaseModel


class RoleResource(BaseModel):
    type: str
    uids: list[str]


class RoleBody(BaseModel):
    name: str
    management: str
    resources: list[RoleResource]
