from typing import Literal

from pydantic import Field

from redis_enterprise_services.config.database_tag import DatabaseTag
from redis_enterprise_services.databases.new_database import NewDatabase


class DatabaseCreationBody(NewDatabase):
    default_user: Literal[True] = True
    tags: list[DatabaseTag]
    authentication_redis_pass: str = Field(repr=False)
