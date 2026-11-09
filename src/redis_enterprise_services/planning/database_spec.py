import re
from typing import Annotated, ClassVar

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from redis_enterprise_services.config.repeated_values import repeated_values
from redis_enterprise_services.config.user_resources_settings import NAME_SEPARATOR
from redis_enterprise_services.databases.new_database import NewDatabase


class DatabaseUserSpec(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    name: str = Field(
        pattern=f"^[^{re.escape(NAME_SEPARATOR)}]+$",
        description="The user name in the cluster, used to connect to the database. "
        "Without '-', and not taken on the cluster.",
        examples=["app"],
    )
    password: str = Field(
        min_length=1,
        description="The user's password. Never returned in any response.",
        examples=["S3cure-Passw0rd"],
    )
    acl_rule: str = Field(
        min_length=1,
        description="A Redis ACL rule for this user on this database: which commands and which keys.",
        examples=["+@all ~orders:*"],
    )


def reject_repeated_users(users: list[DatabaseUserSpec]) -> list[DatabaseUserSpec]:
    names: list[str] = [user.name for user in users]
    repeated: set[str] = repeated_values(values=names)
    if repeated:
        raise ValueError(f"users requested more than once: {sorted(repeated)}")
    return users


type UniqueDatabaseUsers = Annotated[list[DatabaseUserSpec], AfterValidator(reject_repeated_users)]


class DatabaseSpec(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    database: NewDatabase = Field(description="The database to create.")
    users: UniqueDatabaseUsers = Field(
        default_factory=list,
        description="Users to create with the database, each with its own role and ACL "
        "limited to this database. Each name once.",
    )

    def with_database(self, *, database: NewDatabase) -> DatabaseSpec:
        return self.model_copy(update={"database": database})
