from redis import Redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from redis_enterprise_services.config.state_settings import StateSettings


def build_redis_client(*, settings: StateSettings) -> Redis:
    return Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
        url=settings.url.get_secret_value(),
        socket_timeout=settings.socket_timeout_seconds,
        socket_connect_timeout=settings.socket_timeout_seconds,
        retry=Retry(backoff=NoBackoff(), retries=0),
        decode_responses=True,
    )
