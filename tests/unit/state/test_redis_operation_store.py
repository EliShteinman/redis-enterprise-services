from unittest.mock import MagicMock, create_autospec

import pytest
from redis import Redis

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.state.redis_keys import RedisKeys
from redis_enterprise_services.state.redis_operation_store import RedisOperationStore


class Scripts:
    def __init__(self) -> None:
        self.open: MagicMock = MagicMock()
        self.finished: MagicMock = MagicMock()
        client: MagicMock = create_autospec(spec=Redis, instance=True)
        client.register_script.side_effect = [self.open, self.finished, MagicMock()]
        self.store: RedisOperationStore = RedisOperationStore(
            client=client,
            keys=RedisKeys(prefix="res:", hash_tag="state"),
            finished_operation_ttl_seconds=600,
            heartbeat_ttl_seconds=60,
        )


@pytest.mark.parametrize(
    argnames="status",
    argvalues=[OperationStatus.SUCCEEDED, OperationStatus.REJECTED, OperationStatus.ROLLED_BACK],
)
def test_a_finished_operation_is_stored_with_the_expiry(status: OperationStatus) -> None:
    scripts: Scripts = Scripts()

    scripts.store.save(operation=Operation(trace_id="trace-1", status=status))

    assert (scripts.open.call_count, scripts.finished.call_args.kwargs["args"][2]) == (0, 600)


@pytest.mark.parametrize(
    argnames="status", argvalues=[OperationStatus.RUNNING, OperationStatus.REQUIRES_MANUAL_INTERVENTION]
)
def test_an_open_operation_stays_open_without_expiry(status: OperationStatus) -> None:
    scripts: Scripts = Scripts()

    scripts.store.save(operation=Operation(trace_id="trace-1", status=status))

    assert (scripts.open.call_count, scripts.finished.call_count) == (1, 0)
