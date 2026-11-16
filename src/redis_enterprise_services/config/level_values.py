from pydantic import Field, JsonValue, SecretStr

from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.port import Port


class ClusterActiveActiveValues(ConfigModel):
    database: dict[str, JsonValue] = Field(default_factory=dict)


class ActiveActiveValues(ClusterActiveActiveValues):
    crdb: dict[str, JsonValue] = Field(default_factory=dict)


class LevelValues(ConfigModel):
    username: str | None = Field(default=None, min_length=1)
    password: SecretStr | None = Field(default=None, min_length=1)
    default_user_password: SecretStr | None = Field(default=None, min_length=1)
    api_port: Port | None = None
    database: dict[str, JsonValue] = Field(default_factory=dict)


class SharedLevelValues(LevelValues):
    active_active: ActiveActiveValues = Field(default_factory=ActiveActiveValues)


class ClusterValues(LevelValues):
    active_active: ClusterActiveActiveValues = Field(default_factory=ClusterActiveActiveValues)
