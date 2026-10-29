from typing import Literal

from pydantic import Field

from redis_enterprise_services.databases.new_database import NewDatabase


class DatabaseCreationBody(NewDatabase):
    default_user: Literal[True] = True
    authentication_redis_pass: str = Field(repr=False)
