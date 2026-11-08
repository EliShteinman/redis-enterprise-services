from typing import Literal

from pydantic import Field, SecretStr

from redis_enterprise_services.config.database_tag import DatabaseTag
from redis_enterprise_services.databases.new_database import NewDatabase


class DatabaseCreationBody(NewDatabase):
    default_user: Literal[True] = True
    tags: list[DatabaseTag]
    authentication_redis_pass: str = Field(repr=False)


def database_creation_body(
    *, spec: NewDatabase, default_tags: list[DatabaseTag], default_user_password: SecretStr
) -> DatabaseCreationBody:
    return DatabaseCreationBody(
        **spec.model_dump(),
        tags=default_tags,
        authentication_redis_pass=default_user_password.get_secret_value(),
    )
