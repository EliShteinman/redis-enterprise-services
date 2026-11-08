from pydantic import BaseModel

from redis_enterprise_services.planning.database_spec import DatabaseSpec
from redis_enterprise_services.planning.single_site_creation_planner import (
    DATABASE_STEP_KEY,
    PERMISSIONS_STEP_KEY,
    acl_step_key,
    role_step_key,
    user_step_key,
)
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming


class PlannedResource(BaseModel):
    resource_type: str
    name: str


def planned_resources_by_step_key(
    *, spec: DatabaseSpec, resource_naming: UserResourceNaming
) -> dict[str, PlannedResource]:
    database_name: str = spec.database.name
    planned_by_step_key: dict[str, PlannedResource] = {
        DATABASE_STEP_KEY: PlannedResource(resource_type="database", name=database_name),
        PERMISSIONS_STEP_KEY: PlannedResource(resource_type="permissions", name=database_name),
    }
    for user in spec.users:
        planned_by_step_key[acl_step_key(user=user)] = PlannedResource(
            resource_type="acl",
            name=resource_naming.acl_name(database_name=database_name, user_name=user.name),
        )
        planned_by_step_key[role_step_key(user=user)] = PlannedResource(
            resource_type="role",
            name=resource_naming.role_name(database_name=database_name, user_name=user.name),
        )
        planned_by_step_key[user_step_key(user=user)] = PlannedResource(resource_type="user", name=user.name)
    return planned_by_step_key
