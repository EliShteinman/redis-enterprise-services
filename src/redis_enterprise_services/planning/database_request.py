import re
from typing import Annotated, ClassVar

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from redis_enterprise_services.config.decomposition_settings import NAME_SEPARATOR
from redis_enterprise_services.databases.new_database import NewDatabase


class DatabaseUserRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    name: str = Field(pattern=f"^[^{re.escape(NAME_SEPARATOR)}]+$")
    password: str = Field(min_length=1)
    acl: str = Field(min_length=1)


def unique_user_names(users: list[DatabaseUserRequest]) -> list[DatabaseUserRequest]:
    names: list[str] = [user.name for user in users]
    repeated: set[str] = {name for name in names if names.count(name) > 1}
    if repeated:
        raise ValueError(f"users requested more than once: {sorted(repeated)}")
    return users


type DatabaseUsers = Annotated[list[DatabaseUserRequest], AfterValidator(unique_user_names)]


class DatabaseRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    database: NewDatabase
    users: DatabaseUsers = Field(default_factory=list)
