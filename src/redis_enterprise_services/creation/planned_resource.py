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
    type: str
    name: str


def planned_resources(
    *, request: DatabaseCreationRequest, names: UserResourceNames
) -> dict[str, PlannedResource]:
    database: str = request.database.name
    resources: dict[str, PlannedResource] = {
        DATABASE_STEP_KEY: PlannedResource(type="database", name=database),
        PERMISSIONS_STEP_KEY: PlannedResource(type="permissions", name=database),
    }
    for user in request.users:
        resources[acl_step_key(user=user)] = PlannedResource(
            type="acl", name=names.acl_name(database=database, user=user.name)
        )
        resources[role_step_key(user=user)] = PlannedResource(
            type="role", name=names.role_name(database=database, user=user.name)
        )
        resources[user_step_key(user=user)] = PlannedResource(type="user", name=user.name)
    return resources
