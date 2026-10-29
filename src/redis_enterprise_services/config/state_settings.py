from pydantic import BaseModel, NonNegativeInt, PositiveFloat, PositiveInt, SecretStr


class LockSettings(BaseModel):
    wait_timeout_seconds: NonNegativeInt
    poll_seconds: PositiveFloat


class StateSettings(BaseModel):
    host: str
    port: PositiveInt
    username: str
    password: SecretStr
    prefix: str
    finished_ttl_seconds: PositiveInt
    lock: LockSettings
