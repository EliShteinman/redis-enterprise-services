from pydantic import Field, NonNegativeFloat, PositiveFloat, PositiveInt, SecretStr

from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.port import Port


class LockSettings(ConfigModel):
    wait_timeout_seconds: NonNegativeFloat
    poll_interval_seconds: PositiveFloat


class StateSettings(ConfigModel):
    host: str = Field(min_length=1)
    port: Port
    username: str = Field(min_length=1)
    password: SecretStr = Field(min_length=1)
    key_prefix: str = Field(min_length=1)
    hash_tag: str = Field(min_length=1)
    socket_timeout_seconds: PositiveFloat
    finished_ttl_seconds: PositiveInt
    lock: LockSettings
