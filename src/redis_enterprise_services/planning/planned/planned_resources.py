from typing import ClassVar, Final, Literal

from pydantic import BaseModel, ConfigDict

from redis_enterprise_services.planning.keys.creation_step_keys import DATABASE_STEP_KEY, PERMISSIONS_STEP_KEY
from redis_enterprise_services.planning.planned.name_kind import NameKind
from redis_enterprise_services.planning.planned.user_resource_naming import UserResourceNaming
from redis_enterprise_services.planning.planned.user_resources import user_resources
from redis_enterprise_services.planning.spec.database_spec import DatabaseSpec

type PlannedResourceType = NameKind | Literal["permissions", "crdb"]

PERMISSIONS_RESOURCE_TYPE: Final[Literal["permissions"]] = "permissions"
CRDB_RESOURCE_TYPE: Final[Literal["crdb"]] = "crdb"


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
        for resource in user_resources(
            naming=resource_naming, database_name=database_name, user=user
        ).in_creation_order():
            planned_by_step_key[resource.step_key] = PlannedResource(
                resource_type=resource.kind, name=resource.name, uid_step_key=resource.step_key
            )
    if spec.users:
        planned_by_step_key[PERMISSIONS_STEP_KEY] = PlannedResource(
            resource_type=PERMISSIONS_RESOURCE_TYPE, name=database_name, uid_step_key=DATABASE_STEP_KEY
        )
    return planned_by_step_key
