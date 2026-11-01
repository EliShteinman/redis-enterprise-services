from typing import Self

from pydantic import BaseModel, PositiveFloat, PositiveInt, model_validator


class LivenessSettings(BaseModel):
    heartbeat_interval_seconds: PositiveFloat
    heartbeat_ttl_seconds: PositiveInt

    @model_validator(mode="after")
    def beats_before_expiry(self) -> Self:
        if self.heartbeat_interval_seconds >= self.heartbeat_ttl_seconds:
            raise ValueError("a heartbeat must be refreshed before it expires")
        return self
