from typing import Literal

from pydantic import Field, JsonValue

from redis_enterprise_services.databases.new_database import NewDatabase


class DatabaseCreationBody(NewDatabase):
    default_user: Literal[True] = True
    tags: list[JsonValue] = Field(default_factory=list)
    authentication_redis_pass: str = Field(repr=False)
