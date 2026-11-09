import pytest
from redis import Redis

from redis_enterprise_services.config.settings import Settings
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.state.redis_keys import RedisKeys
from redis_enterprise_services.state.redis_operation_store import RedisOperationStore
from redis_enterprise_services.state.tracked_record_writer import TrackedRecordWriter


@pytest.fixture
def store(client: Redis, keys: RedisKeys, settings: Settings) -> RedisOperationStore:
    return RedisOperationStore(
        client=client,
        keys=keys,
        record_writer=TrackedRecordWriter(client=client),
        finished_ttl_seconds=settings.state.finished_ttl_seconds,
        heartbeat_ttl_seconds=settings.liveness.heartbeat_ttl_seconds,
    )


def running(trace_id: str) -> Operation:
    return Operation(trace_id=trace_id, status=OperationStatus.RUNNING)


def is_open(client: Redis, keys: RedisKeys, trace_id: str) -> bool:
    return bool(client.sismember(keys.open_trace_ids(), trace_id))


def test_a_new_operation_starts_with_a_heartbeat(
    client: Redis, keys: RedisKeys, store: RedisOperationStore, trace_id: str
) -> None:
    store.create_if_absent(operation=running(trace_id))

    assert client.ttl(keys.heartbeat(trace_id=trace_id)) > 0


def test_a_new_operation_is_open(
    client: Redis, keys: RedisKeys, store: RedisOperationStore, trace_id: str
) -> None:
    store.create_if_absent(operation=running(trace_id))

    assert is_open(client, keys, trace_id)


def test_an_existing_operation_is_returned_instead_of_created(
    store: RedisOperationStore, trace_id: str
) -> None:
    store.create_if_absent(operation=running(trace_id))

    assert store.create_if_absent(operation=running(trace_id)) == running(trace_id)


def test_a_cleanly_ended_operation_expires_and_leaves_the_open_set(
    client: Redis, keys: RedisKeys, store: RedisOperationStore, trace_id: str
) -> None:
    store.create_if_absent(operation=running(trace_id))

    store.save(operation=Operation(trace_id=trace_id, status=OperationStatus.SUCCEEDED))

    assert (
        is_open(client, keys, trace_id),
        client.ttl(keys.operation(trace_id=trace_id)) > 0,
    ) == (
        False,
        True,
    )


def test_a_running_operation_stays_open_without_expiry(
    client: Redis, keys: RedisKeys, store: RedisOperationStore, trace_id: str
) -> None:
    store.save(operation=running(trace_id))

    assert (is_open(client, keys, trace_id), client.ttl(keys.operation(trace_id=trace_id))) == (True, -1)
