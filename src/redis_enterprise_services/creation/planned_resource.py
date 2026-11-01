from pydantic import BaseModel

from redis_enterprise_services.planning.database_request import DatabaseRequest
from redis_enterprise_services.planning.resource_names import ResourceNames
from redis_enterprise_services.planning.single_site_creation import (
    DATABASE_KEY,
    PERMISSIONS_KEY,
    acl_key,
    role_key,
    user_key,
)


class PlannedResource(BaseModel):
    type: str
    name: str


def planned_resources(*, request: DatabaseRequest, names: ResourceNames) -> dict[str, PlannedResource]:
    database: str = request.database.name
    resources: dict[str, PlannedResource] = {
        DATABASE_KEY: PlannedResource(type="database", name=database),
        PERMISSIONS_KEY: PlannedResource(type="permissions", name=database),
    }
    for user in request.users:
        resources[acl_key(user=user)] = PlannedResource(
            type="acl", name=names.acl(database=database, user=user.name)
        )
        resources[role_key(user=user)] = PlannedResource(
            type="role", name=names.role(database=database, user=user.name)
        )
        resources[user_key(user=user)] = PlannedResource(type="user", name=user.name)
    return resources
