from pydantic import BaseModel, NonNegativeFloat, PositiveInt


class RetrySettings(BaseModel):
    attempts: PositiveInt
    backoff_seconds: NonNegativeFloat


class SagaSettings(BaseModel):
    step_retry: RetrySettings
    compensation_retry: RetrySettings
    transient_error_codes: frozenset[str]
