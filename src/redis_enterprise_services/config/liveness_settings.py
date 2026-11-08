from typing import Self

from pydantic import PositiveFloat, PositiveInt, model_validator

from redis_enterprise_services.config.config_model import ConfigModel


class LivenessSettings(ConfigModel):
    heartbeat_interval_seconds: PositiveFloat
    heartbeat_ttl_seconds: PositiveInt
    min_heartbeats_per_ttl: PositiveInt
    sweep_interval_seconds: PositiveFloat

    @model_validator(mode="after")
    def heartbeat_refreshed_before_expiry(self) -> Self:
        if self.heartbeat_interval_seconds * self.min_heartbeats_per_ttl > self.heartbeat_ttl_seconds:
            raise ValueError(
                f"a heartbeat must be refreshed at least {self.min_heartbeats_per_ttl} times before it ends"
            )
        return self
