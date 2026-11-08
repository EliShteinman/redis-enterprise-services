from pydantic import PositiveFloat

from redis_enterprise_services.config.config_model import ConfigModel


class WaitSettings(ConfigModel):
    interval_seconds: PositiveFloat
    timeout_seconds: PositiveFloat
