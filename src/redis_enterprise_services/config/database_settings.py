from typing import Annotated

from pydantic import AfterValidator, Field, SecretStr

from redis_enterprise_services.config.database_tag import DatabaseTag
from redis_enterprise_services.config.repeated_values import reject_repeated
from redis_enterprise_services.config.resource_settings import ResourceSettings
from redis_enterprise_services.config.wait_settings import WaitSettings


def reject_repeated_tag_keys(tags: list[DatabaseTag]) -> list[DatabaseTag]:
    reject_repeated(what="default tag keys", values=[tag.key for tag in tags])
    return tags


class DatabaseSettings(ResourceSettings):
    default_user_password: SecretStr = Field(min_length=1)
    default_tags: Annotated[list[DatabaseTag], AfterValidator(reject_repeated_tag_keys)]
    active_status: str
    required_fields: list[str]
    endpoints_field: str
    endpoint_fields: list[str]
    creation_failed_status: str
    order_insensitive_fields: frozenset[str]
    wait: WaitSettings
