import re
from typing import Annotated, ClassVar

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from redis_enterprise_services.config.repeated_values import repeated_values
from redis_enterprise_services.config.user_resources_settings import NAME_SEPARATOR
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.planning.acl_rule_syntax import ACL_RULE_PATTERN, REDIS_MIN_PASSWORD_LENGTH


class DatabaseUserSpec(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    name: str = Field(
        pattern=f"^[^{re.escape(NAME_SEPARATOR)}]+$",
        description="The user name in the cluster, used to connect to the database. "
        "Without '-', and not taken on the cluster.",
        examples=["app"],
    )
    password: str = Field(
        min_length=REDIS_MIN_PASSWORD_LENGTH,
        description="The user's password, at least 8 characters (Redis's lowest password_min_length; a "
        "cluster set higher refuses a shorter one). The result returns it in the user's permission: the "
        "cluster never returns a password, so it is the one the cluster accepted when it created the user.",
        examples=["S3cure-Passw0rd"],
    )
    acl_rule: str = Field(
        pattern=ACL_RULE_PATTERN,
        description="A Redis ACL rule for this user on this database: which commands and which keys. "
        "Words separated by spaces: +@category, -@category, +command, -command|subcommand, ~keys, "
        "%R~keys, %W~keys, %RW~keys, &channels, allkeys, allcommands, nocommands, resetkeys, allchannels, "
        "resetchannels, on, off, and selectors in parentheses. The cluster checks that the commands and "
        "categories exist.",
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
