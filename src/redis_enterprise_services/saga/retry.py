import time

from redis_enterprise_services.config.saga_settings import RetrySettings


def pause(*, retry: RetrySettings, attempt: int) -> None:
    time.sleep(retry.backoff_seconds * attempt)
