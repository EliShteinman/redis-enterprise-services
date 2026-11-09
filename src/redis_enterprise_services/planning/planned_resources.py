from typing import ClassVar, Final, Literal

from pydantic import BaseModel, ConfigDict

from redis_enterprise_services.planning.creation_step_keys import (
    DATABASE_STEP_KEY,
    PERMISSIONS_STEP_KEY,
    acl_step_key,
    role_step_key,
    user_step_key,
)
from redis_enterprise_services.planning.database_spec import DatabaseSpec
from redis_enterprise_services.planning.name_kind import NameKind
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming

type PlannedResourceType = NameKind | Literal["permissions"]

PERMISSIONS_RESOURCE_TYPE: Final[Literal["permissions"]] = "permissions"


class PlannedResource(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    resource_type: PlannedResourceType
    name: str
    uid_step_key: str


def planned_resources_by_step_key(
    *, spec: DatabaseSpec, resource_naming: UserResourceNaming
) -> dict[str, PlannedResource]:
    database_name: str = spec.database.name
    planned_by_step_key: dict[str, PlannedResource] = {
        DATABASE_STEP_KEY: PlannedResource(
            resource_type="database", name=database_name, uid_step_key=DATABASE_STEP_KEY
        ),
    }
    for user in spec.users:
        planned_by_step_key[acl_step_key(user=user)] = PlannedResource(
            resource_type="acl",
            name=resource_naming.acl_name(database_name=database_name, user_name=user.name),
            uid_step_key=acl_step_key(user=user),
        )
        planned_by_step_key[role_step_key(user=user)] = PlannedResource(
            resource_type="role",
            name=resource_naming.role_name(database_name=database_name, user_name=user.name),
            uid_step_key=role_step_key(user=user),
        )
        planned_by_step_key[user_step_key(user=user)] = PlannedResource(
            resource_type="user", name=user.name, uid_step_key=user_step_key(user=user)
        )
    if spec.users:
        planned_by_step_key[PERMISSIONS_STEP_KEY] = PlannedResource(
            resource_type=PERMISSIONS_RESOURCE_TYPE, name=database_name, uid_step_key=DATABASE_STEP_KEY
        )
    return planned_by_step_key
