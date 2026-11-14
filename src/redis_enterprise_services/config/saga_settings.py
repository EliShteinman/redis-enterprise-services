from pydantic import NonNegativeFloat, PositiveInt

from redis_enterprise_services.config.config_model import ConfigModel


class RetrySettings(ConfigModel):
    attempts: PositiveInt
    backoff_step_seconds: NonNegativeFloat


class SagaSettings(ConfigModel):
    step_retry: RetrySettings
    compensation_retry: RetrySettings
