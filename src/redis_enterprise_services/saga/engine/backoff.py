from redis_enterprise_services.config.saga_settings import RetrySettings
from redis_enterprise_services.timing.sleeper import Sleeper


def wait_before_retry(*, retry_settings: RetrySettings, attempt: int, sleeper: Sleeper) -> None:
    sleeper.sleep(seconds=retry_settings.backoff_seconds * attempt)
