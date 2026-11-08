from pydantic import JsonValue

from redis_enterprise_services.config.role_settings import RoleSettings
from redis_enterprise_services.resources.endpoint_resource_repository import EndpointResourceRepository
from redis_enterprise_services.resources.resource_endpoint import ResourceEndpoint
from redis_enterprise_services.roles.creation_body import RoleCreationBody, RoleResourceScope
from redis_enterprise_services.roles.models import NewRole


class RoleRepository(EndpointResourceRepository[NewRole]):
    def __init__(self, *, endpoint: ResourceEndpoint, settings: RoleSettings) -> None:
        super().__init__(endpoint=endpoint)
        self._settings: RoleSettings = settings

    def creation_body(self, *, spec: NewRole) -> dict[str, JsonValue]:
        return RoleCreationBody(
            name=spec.name,
            management=spec.management,
            resources=[
                RoleResourceScope(
                    type=self._settings.database_resource_type, uids=[str(uid) for uid in spec.database_uids]
                )
            ],
        ).model_dump()
