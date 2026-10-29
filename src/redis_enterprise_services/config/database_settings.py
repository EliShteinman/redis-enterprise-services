from pydantic import SecretStr

from redis_enterprise_services.config.resource_settings import ResourceSettings
from redis_enterprise_services.config.wait_settings import WaitSettings


class DatabaseSettings(ResourceSettings):
    default_user_password: SecretStr
    active_status: str
    creation_failed_status: str
    wait: WaitSettings
