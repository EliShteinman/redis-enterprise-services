from pydantic import BaseModel

from redis_enterprise_services.roles.models import RoleManagement


class RoleResource(BaseModel):
    type: str
    uids: list[str]


class RoleBody(BaseModel):
    name: str
    management: RoleManagement
    resources: list[RoleResource]
