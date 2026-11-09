import secrets
from collections.abc import Iterator

import pytest
from pydantic import ValidationError
from redis import Redis
from redis.exceptions import RedisError

from redis_enterprise_services.config.settings import Settings, load_settings
from redis_enterprise_services.state.redis_client import build_redis_client
from redis_enterprise_services.state.redis_keys import RedisKeys

TRACE_ID_PREFIX: str = "itest"
PROBE_KEY: str = "res:itest-probe"
LOCK_KEY_KINDS: tuple[str, ...] = ("database", "user")


@pytest.fixture(scope="session")
def settings() -> Settings:
    try:
        return load_settings()
    except ValidationError:
        pytest.skip(reason="the RES_ settings of the local clusters are not set")


@pytest.fixture(scope="session")
def client(settings: Settings) -> Iterator[Redis]:
    redis_client: Redis = build_redis_client(settings=settings.state)
    try:
        redis_client.exists(PROBE_KEY)
    except RedisError:
        pytest.skip(reason="the saga-state Redis of the local clusters is not reachable")
    yield redis_client
    redis_client.close()


@pytest.fixture(scope="session")
def keys(settings: Settings) -> RedisKeys:
    return RedisKeys(key_prefix=settings.state.key_prefix, hash_tag=settings.state.hash_tag)


@pytest.fixture
def trace_id(client: Redis, keys: RedisKeys) -> Iterator[str]:
    test_trace_id: str = TRACE_ID_PREFIX + secrets.token_hex(nbytes=12)
    yield test_trace_id
    client.delete(
        keys.operation(trace_id=test_trace_id),
        keys.heartbeat(trace_id=test_trace_id),
        keys.saga_record(saga_id=test_trace_id),
        keys.held_locks(owner=test_trace_id),
        *[keys.lock(lock_key=f"https://itest:9443/{kind}/{test_trace_id}") for kind in LOCK_KEY_KINDS],
    )
    client.srem(keys.open_trace_ids(), test_trace_id)
    client.srem(keys.unfinished_saga_ids(), test_trace_id)


@pytest.fixture
def lock_keys(trace_id: str) -> list[str]:
    return [f"https://itest:9443/{kind}/{trace_id}" for kind in LOCK_KEY_KINDS]
