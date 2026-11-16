from typing import TypeIs

from redis_enterprise_services.planning.availability.requested_name import RequestedName
from redis_enterprise_services.planning.planned.name_kind import NAME_KINDS, NameKind
from redis_enterprise_services.planning.planned.planned_resources import (
    PlannedResourceType,
    planned_resources_by_step_key,
)
from redis_enterprise_services.planning.planned.user_resource_naming import UserResourceNaming
from redis_enterprise_services.planning.spec.database_spec import DatabaseSpec


class CreationNaming:
    def __init__(self, *, resource_naming: UserResourceNaming) -> None:
        self._resource_naming: UserResourceNaming = resource_naming

    def requested_names(self, *, spec: DatabaseSpec) -> list[RequestedName]:
        return [
            RequestedName(kind=planned.resource_type, name=planned.name)
            for planned in planned_resources_by_step_key(
                spec=spec, resource_naming=self._resource_naming
            ).values()
            if is_name_kind(resource_type=planned.resource_type)
        ]


def is_name_kind(*, resource_type: PlannedResourceType) -> TypeIs[NameKind]:
    return resource_type in NAME_KINDS
