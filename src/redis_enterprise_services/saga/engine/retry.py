from redis_enterprise_services.config.saga_settings import RetrySettings
from redis_enterprise_services.timing.sleeper import Sleeper


def pause(*, retry: RetrySettings, attempt: int, sleeper: Sleeper) -> None:
    sleeper.sleep(seconds=retry.backoff_seconds * attempt)
