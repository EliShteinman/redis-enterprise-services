from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.config.database_tag import DatabaseTag
from redis_enterprise_services.databases.creation_body import database_creation_body
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.resources.creation_body_builder import CreationBodyBuilder


class DatabaseCreationBodyBuilder(CreationBodyBuilder[NewDatabase]):
    def __init__(
        self, *, default_user_password_by_api_url: dict[str, SecretStr], default_tags: list[DatabaseTag]
    ) -> None:
        self._default_user_password_by_api_url: dict[str, SecretStr] = default_user_password_by_api_url
        self._default_tags: list[DatabaseTag] = default_tags

    def creation_body(self, *, spec: NewDatabase, cluster: ClusterAddress) -> dict[str, JsonValue]:
        return database_creation_body(
            spec=spec,
            default_tags=self._default_tags,
            default_user_password=self._default_user_password_by_api_url[cluster.api_url],
        ).model_dump(exclude_none=True)
