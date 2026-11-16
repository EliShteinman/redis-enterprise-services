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

ERROR: PublicError = PublicError(code="internal_error", kind="needs_investigation", message="internal error")


@pytest.mark.parametrize(
    argnames=("status", "ttl_seconds", "is_tracked"),
    argvalues=[
        (OperationStatus.SUCCEEDED, 600, False),
        (OperationStatus.REJECTED, 600, False),
        (OperationStatus.ROLLED_BACK, 600, False),
        (OperationStatus.RUNNING, 0, True),
        (OperationStatus.REQUIRES_MANUAL_INTERVENTION, 0, False),
    ],
)
def test_only_a_cleanly_ended_operation_expires_and_only_a_running_one_stays_open(
    status: OperationStatus, ttl_seconds: int, is_tracked: bool
) -> None:
    record_writer: MagicMock = create_autospec(spec=TrackedRecordWriter, instance=True)
    store: RedisOperationStore = RedisOperationStore(
        client=create_autospec(spec=Redis, instance=True),
        keys=RedisKeys(key_prefix="res:"),
        record_writer=record_writer,
        finished_ttl_seconds=600,
        heartbeat_ttl_seconds=60,
    )

    error: PublicError | None = None if status in STATUSES_WITHOUT_ERROR else ERROR
    store.save(operation=Operation(trace_id="trace-1", status=status, error=error))

    saved: dict[str, object] = record_writer.save.call_args.kwargs
    assert (saved["ttl_seconds"], saved["is_tracked"]) == (ttl_seconds, is_tracked)


def test_an_unreadable_operation_record_raises_a_project_error() -> None:
    client: MagicMock = create_autospec(spec=Redis, instance=True)
    client.get.return_value = '{"status": "unknown"}'
    store: RedisOperationStore = RedisOperationStore(
        client=client,
        keys=RedisKeys(key_prefix="res:"),
        record_writer=create_autospec(spec=TrackedRecordWriter, instance=True),
        finished_ttl_seconds=600,
        heartbeat_ttl_seconds=60,
    )

    with pytest.raises(expected_exception=UnreadableOperationRecordError):
        store.find(trace_id="trace-1")
