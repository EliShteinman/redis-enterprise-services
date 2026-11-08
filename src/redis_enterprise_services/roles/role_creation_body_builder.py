from pydantic import JsonValue

from redis_enterprise_services.config.role_settings import RoleSettings
from redis_enterprise_services.resources.creation_body_builder import CreationBodyBuilder
from redis_enterprise_services.roles.creation_body import role_creation_body
from redis_enterprise_services.roles.models import NewRole


class RoleCreationBodyBuilder(CreationBodyBuilder[NewRole]):
    def __init__(self, *, settings: RoleSettings) -> None:
        self._settings: RoleSettings = settings

    def creation_body(self, *, spec: NewRole) -> dict[str, JsonValue]:
        return role_creation_body(
            spec=spec, database_resource_type=self._settings.database_resource_type
        ).model_dump()
