from pydantic import BaseModel

from redis_enterprise_services.planning.database_creation_request import DatabaseCreationRequest
from redis_enterprise_services.planning.single_site_creation_planner import (
    DATABASE_STEP_KEY,
    PERMISSIONS_STEP_KEY,
    acl_step_key,
    role_step_key,
    user_step_key,
)
from redis_enterprise_services.planning.user_resource_names import UserResourceNames


class PlannedResource(BaseModel):
    resource_type: str
    name: str


def planned_resources_by_step_key(
    *, request: DatabaseCreationRequest, resource_names: UserResourceNames
) -> dict[str, PlannedResource]:
    database_name: str = request.database.name
    planned_by_step_key: dict[str, PlannedResource] = {
        DATABASE_STEP_KEY: PlannedResource(resource_type="database", name=database_name),
        PERMISSIONS_STEP_KEY: PlannedResource(resource_type="permissions", name=database_name),
    }
    for user in request.users:
        planned_by_step_key[acl_step_key(user=user)] = PlannedResource(
            resource_type="acl", name=resource_names.acl_name(database=database_name, user=user.name)
        )
        planned_by_step_key[role_step_key(user=user)] = PlannedResource(
            resource_type="role", name=resource_names.role_name(database=database_name, user=user.name)
        )
        planned_by_step_key[user_step_key(user=user)] = PlannedResource(resource_type="user", name=user.name)
    return planned_by_step_key
