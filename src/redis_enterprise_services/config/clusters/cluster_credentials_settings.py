from pydantic import Field, SecretStr

from redis_enterprise_services.config.config_model import ConfigModel


class ClusterCredentialsSettings(ConfigModel):
    username: str = Field(min_length=1)
    password: SecretStr = Field(min_length=1)
