from pydantic import JsonValue, SecretStr

from redis_enterprise_services.databases.creation_body import DatabaseCreationBody
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.resources.endpoint_repository import EndpointRepository
from redis_enterprise_services.resources.resource_calls import ResourceCalls


class DatabaseLifecycle(EndpointRepository[NewDatabase]):
    def __init__(self, *, endpoint: ResourceCalls, default_user_password: SecretStr) -> None:
        super().__init__(endpoint=endpoint)
        self._default_user_password: SecretStr = default_user_password

    def creation_body(self, *, spec: NewDatabase) -> dict[str, JsonValue]:
        return DatabaseCreationBody(
            **spec.model_dump(), authentication_redis_pass=self._default_user_password.get_secret_value()
        ).model_dump(exclude_none=True)
