from unittest.mock import MagicMock, create_autospec

import pytest
from redis import Redis

from redis_enterprise_services.exceptions.operation import UnreadableOperationRecordError
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import STATUSES_WITHOUT_ERROR, OperationStatus
from redis_enterprise_services.operations.public_error import PublicError
from redis_enterprise_services.state.redis_keys import RedisKeys
from redis_enterprise_services.state.redis_operation_store import RedisOperationStore
from redis_enterprise_services.state.tracked_record_writer import TrackedRecordWriter

ERROR: PublicError = PublicError(code="internal_error", message="internal error")


@pytest.mark.parametrize(
    argnames=("status", "ttl_seconds"),
    argvalues=[
        (OperationStatus.SUCCEEDED, 600),
        (OperationStatus.REJECTED, 600),
        (OperationStatus.ROLLED_BACK, 600),
        (OperationStatus.RUNNING, 0),
        (OperationStatus.REQUIRES_MANUAL_INTERVENTION, 0),
    ],
)
def test_only_an_operation_in_an_expiring_status_is_stored_with_the_expiry(
    status: OperationStatus, ttl_seconds: int
) -> None:
    record_writer: MagicMock = create_autospec(spec=TrackedRecordWriter, instance=True)
    store: RedisOperationStore = RedisOperationStore(
        client=create_autospec(spec=Redis, instance=True),
        keys=RedisKeys(key_prefix="res:", hash_tag="state"),
        record_writer=record_writer,
        finished_ttl_seconds=600,
        heartbeat_ttl_seconds=60,
    )

    error: PublicError | None = None if status in STATUSES_WITHOUT_ERROR else ERROR
    store.save(operation=Operation(trace_id="trace-1", status=status, error=error))

    assert record_writer.save.call_args.kwargs["ttl_seconds"] == ttl_seconds


def test_an_unreadable_operation_record_raises_a_project_error() -> None:
    client: MagicMock = create_autospec(spec=Redis, instance=True)
    client.get.return_value = '{"status": "unknown"}'
    store: RedisOperationStore = RedisOperationStore(
        client=client,
        keys=RedisKeys(key_prefix="res:", hash_tag="state"),
        record_writer=create_autospec(spec=TrackedRecordWriter, instance=True),
        finished_ttl_seconds=600,
        heartbeat_ttl_seconds=60,
    )

    with pytest.raises(expected_exception=UnreadableOperationRecordError):
        store.find(trace_id="trace-1")
