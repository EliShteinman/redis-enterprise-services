from pydantic import Field, JsonValue, SecretStr

from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.validation.port import Port


class ActiveActiveValues(ConfigModel):
    database: dict[str, JsonValue] = Field(default_factory=dict)
    crdb: dict[str, JsonValue] = Field(default_factory=dict)


class LevelValues(ConfigModel):
    username: str | None = Field(default=None, min_length=1)
    password: SecretStr | None = Field(default=None, min_length=1)
    default_user_password: SecretStr | None = Field(default=None, min_length=1)
    api_port: Port | None = None
    database: dict[str, JsonValue] = Field(default_factory=dict)


class EnvironmentOrNetworkValues(LevelValues):
    active_active: ActiveActiveValues = Field(default_factory=ActiveActiveValues)
