from pydantic import BaseModel

from redis_enterprise_services.config.role_management import RoleManagement
from redis_enterprise_services.roles.models import NewRole


class RoleResourceScope(BaseModel):
    type: str
    uids: list[str]


class RoleCreationBody(BaseModel):
    name: str
    management: RoleManagement
    resources: list[RoleResourceScope]


def database_scope(*, resource_type: str, database_uids: list[int]) -> RoleResourceScope:
    return RoleResourceScope(type=resource_type, uids=[str(uid) for uid in database_uids])


def role_creation_body(*, spec: NewRole, database_resource_type: str) -> RoleCreationBody:
    return RoleCreationBody(
        name=spec.name,
        management=spec.management,
        resources=[database_scope(resource_type=database_resource_type, database_uids=spec.database_uids)],
    )
