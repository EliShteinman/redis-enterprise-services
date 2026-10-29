from pydantic import Field, SecretStr

from redis_enterprise_services.config.database_tag import DatabaseTag
from redis_enterprise_services.config.resource_settings import ResourceSettings
from redis_enterprise_services.config.wait_settings import WaitSettings


class DatabaseSettings(ResourceSettings):
    default_user_password: SecretStr = Field(min_length=1)
    default_tags: list[DatabaseTag]
    active_status: str
    creation_failed_status: str
    wait: WaitSettings
