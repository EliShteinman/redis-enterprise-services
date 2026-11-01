from typing import Self

from pydantic import BaseModel, PositiveFloat, PositiveInt, model_validator


class LivenessSettings(BaseModel):
    heartbeat_interval_seconds: PositiveFloat
    heartbeat_ttl_seconds: PositiveInt
    min_beats_per_ttl: PositiveInt
    sweep_interval_seconds: PositiveFloat

    @model_validator(mode="after")
    def beats_before_expiry(self) -> Self:
        if self.heartbeat_interval_seconds * self.min_beats_per_ttl > self.heartbeat_ttl_seconds:
            raise ValueError(
                f"a heartbeat must be refreshed at least {self.min_beats_per_ttl} times before it expires"
            )
        return self
