from pydantic import Field, NonNegativeFloat, PositiveFloat, PositiveInt

from redis_enterprise_services.config.config_model import ConfigModel
from redis_enterprise_services.config.redis_connection_url import RedisConnectionUrl


class LockSettings(ConfigModel):
    wait_timeout_seconds: NonNegativeFloat
    poll_interval_seconds: PositiveFloat


class StateSettings(ConfigModel):
    url: RedisConnectionUrl
    key_prefix: str = Field(min_length=1)
    socket_timeout_seconds: PositiveFloat
    finished_ttl_seconds: PositiveInt
    lock: LockSettings
