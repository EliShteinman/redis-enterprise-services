from pydantic import BaseModel

from redis_enterprise_services.config.role_management import RoleManagement


class RoleResourceScope(BaseModel):
    type: str
    uids: list[str]


class RoleCreationBody(BaseModel):
    name: str
    management: RoleManagement
    resources: list[RoleResourceScope]
