from pydantic import JsonValue

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.config.resource_settings import RoleSettings
from redis_enterprise_services.resources.endpoint import ResourceEndpoint
from redis_enterprise_services.resources.models import CreatedResource, NamedResource
from redis_enterprise_services.roles.models import NewRole


class RoleRepository:
    def __init__(self, *, endpoint: ResourceEndpoint, settings: RoleSettings) -> None:
        self._endpoint: ResourceEndpoint = endpoint
        self._settings: RoleSettings = settings

    def create(self, *, target: ClusterTarget, spec: NewRole) -> CreatedResource:
        return self._endpoint.create(target=target, body=self.creation_body(role=spec))

    def delete(self, *, target: ClusterTarget, uid: int) -> str | None:
        return self._endpoint.delete(target=target, uid=uid)

    def find_by_name(self, *, target: ClusterTarget, name: str) -> NamedResource | None:
        return self._endpoint.find_by_name(target=target, name=name)

    def creation_body(self, *, role: NewRole) -> dict[str, JsonValue]:
        return {
            "name": role.name,
            "management": role.management,
            "resources": [
                {
                    "type": self._settings.database_resource_type,
                    "uids": [str(uid) for uid in role.database_uids],
                }
            ],
        }
