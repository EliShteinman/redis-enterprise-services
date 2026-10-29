from pydantic import JsonValue

from redis_enterprise_services.config.resource_settings import RoleSettings
from redis_enterprise_services.resources.endpoint_repository import EndpointRepository
from redis_enterprise_services.resources.resource_calls import ResourceCalls
from redis_enterprise_services.roles.models import NewRole


class RoleRepository(EndpointRepository[NewRole]):
    def __init__(self, *, endpoint: ResourceCalls, settings: RoleSettings) -> None:
        super().__init__(endpoint=endpoint)
        self._settings: RoleSettings = settings

    def creation_body(self, *, spec: NewRole) -> dict[str, JsonValue]:
        return {
            "name": spec.name,
            "management": spec.management,
            "resources": [
                {
                    "type": self._settings.database_resource_type,
                    "uids": [str(uid) for uid in spec.database_uids],
                }
            ],
        }
