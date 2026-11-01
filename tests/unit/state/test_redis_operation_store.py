from unittest.mock import MagicMock, create_autospec

import pytest
from redis import Redis

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.state.redis_keys import RedisKeys
from redis_enterprise_services.state.redis_operation_store import RedisOperationStore


def stored_expiry(*, status: OperationStatus) -> int | None:
    client: MagicMock = create_autospec(spec=Redis, instance=True)
    store: RedisOperationStore = RedisOperationStore(
        client=client, keys=RedisKeys(prefix="res:", hash_tag="state"), finished_ttl_seconds=600
    )

    store.save(operation=Operation(trace_id="trace-1", status=status))

    return client.set.call_args.kwargs["ex"]


@pytest.mark.parametrize(
    argnames="status",
    argvalues=[OperationStatus.SUCCEEDED, OperationStatus.REJECTED, OperationStatus.ROLLED_BACK],
)
def test_a_finished_operation_is_stored_with_the_expiry(status: OperationStatus) -> None:
    assert stored_expiry(status=status) == 600


@pytest.mark.parametrize(
    argnames="status", argvalues=[OperationStatus.RUNNING, OperationStatus.REQUIRES_MANUAL_INTERVENTION]
)
def test_an_open_operation_is_stored_without_expiry(status: OperationStatus) -> None:
    assert stored_expiry(status=status) is None
