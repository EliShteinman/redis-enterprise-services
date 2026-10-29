from pydantic import BaseModel, Field, NonNegativeInt, PositiveFloat, PositiveInt, SecretStr


class LockSettings(BaseModel):
    wait_timeout_seconds: NonNegativeInt
    poll_seconds: PositiveFloat


class StateSettings(BaseModel):
    host: str
    port: PositiveInt
    username: str
    password: SecretStr
    prefix: str = Field(min_length=1)
    hash_tag: str = Field(min_length=1)
    socket_timeout_seconds: PositiveFloat
    command_retries: NonNegativeInt
    finished_ttl_seconds: PositiveInt
    lock: LockSettings
