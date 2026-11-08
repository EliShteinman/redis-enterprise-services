from pydantic import BaseModel, Field, NonNegativeInt, PositiveFloat, PositiveInt, SecretStr

from redis_enterprise_services.config.port import Port


class LockSettings(BaseModel):
    wait_timeout_seconds: NonNegativeInt
    poll_seconds: PositiveFloat


class StateSettings(BaseModel):
    host: str
    port: Port
    username: str
    password: SecretStr = Field(min_length=1)
    prefix: str = Field(min_length=1)
    hash_tag: str = Field(min_length=1)
    socket_timeout_seconds: PositiveFloat
    finished_ttl_seconds: PositiveInt
    lock: LockSettings
