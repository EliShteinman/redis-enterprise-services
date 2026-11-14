from redis_enterprise_services.planning.availability.requested_name import RequestedName
from redis_enterprise_services.planning.database_spec import DatabaseSpec
from redis_enterprise_services.planning.planned_resources import (
    PERMISSIONS_RESOURCE_TYPE,
    planned_resources_by_step_key,
)
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming


class CreationNaming:
    def __init__(self, *, resource_naming: UserResourceNaming) -> None:
        self._resource_naming: UserResourceNaming = resource_naming

    def requested_names(self, *, spec: DatabaseSpec) -> list[RequestedName]:
        return [
            RequestedName(kind=planned.resource_type, name=planned.name)
            for planned in planned_resources_by_step_key(
                spec=spec, resource_naming=self._resource_naming
            ).values()
            if planned.resource_type != PERMISSIONS_RESOURCE_TYPE
        ]
