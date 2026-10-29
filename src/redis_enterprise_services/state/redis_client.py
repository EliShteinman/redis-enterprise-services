from redis import Redis

from redis_enterprise_services.config.state_settings import StateSettings


def build_redis_client(*, settings: StateSettings) -> Redis:
    return Redis(
        host=settings.host,
        port=settings.port,
        username=settings.username,
        password=settings.password.get_secret_value(),
        decode_responses=True,
    )
