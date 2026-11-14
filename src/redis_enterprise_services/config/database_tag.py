from pydantic import Field

from redis_enterprise_services.config.config_model import ConfigModel


class DatabaseTag(ConfigModel):
    key: str = Field(pattern=r'^[^&<>"]+$')
    value: str
