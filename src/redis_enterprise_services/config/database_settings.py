from typing import Annotated

from pydantic import AfterValidator, Field, SecretStr

from redis_enterprise_services.config.database_tag import DatabaseTag
from redis_enterprise_services.config.resource_settings import ResourceSettings
from redis_enterprise_services.config.wait_settings import WaitSettings


def reject_repeated_tag_keys(tags: list[DatabaseTag]) -> list[DatabaseTag]:
    keys: list[str] = [tag.key for tag in tags]
    repeated: set[str] = {key for key in keys if keys.count(key) > 1}
    if repeated:
        raise ValueError(f"default tags repeat keys: {sorted(repeated)}")
    return tags


class DatabaseSettings(ResourceSettings):
    default_user_password: SecretStr = Field(min_length=1)
    default_tags: Annotated[list[DatabaseTag], AfterValidator(reject_repeated_tag_keys)]
    active_status: str
    creation_failed_status: str
    order_insensitive_fields: frozenset[str]
    wait: WaitSettings
