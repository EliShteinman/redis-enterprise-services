from unittest.mock import MagicMock, create_autospec

import pytest
from redis import Redis

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.state.redis_keys import RedisKeys
from redis_enterprise_services.state.redis_operation_store import RedisOperationStore


class StoreWithMockedScripts:
    def __init__(self) -> None:
        self.save_without_expiry: MagicMock = MagicMock()
        self.save_with_expiry: MagicMock = MagicMock()
        client: MagicMock = create_autospec(spec=Redis, instance=True)
        client.register_script.side_effect = [self.save_without_expiry, self.save_with_expiry, MagicMock()]
        self.store: RedisOperationStore = RedisOperationStore(
            client=client,
            keys=RedisKeys(key_prefix="res:", hash_tag="state"),
            finished_ttl_seconds=600,
            heartbeat_ttl_seconds=60,
        )


@pytest.mark.parametrize(
    argnames="status",
    argvalues=[OperationStatus.SUCCEEDED, OperationStatus.REJECTED, OperationStatus.ROLLED_BACK],
)
def test_an_operation_in_an_expiring_status_is_stored_with_the_expiry(status: OperationStatus) -> None:
    scripts: StoreWithMockedScripts = StoreWithMockedScripts()

    scripts.store.save(operation=Operation(trace_id="trace-1", status=status))

    assert (scripts.save_without_expiry.call_count, scripts.save_with_expiry.call_args.kwargs["args"][2]) == (
        0,
        600,
    )


@pytest.mark.parametrize(
    argnames="status", argvalues=[OperationStatus.RUNNING, OperationStatus.REQUIRES_MANUAL_INTERVENTION]
)
def test_an_operation_in_a_non_expiring_status_is_stored_without_expiry(status: OperationStatus) -> None:
    scripts: StoreWithMockedScripts = StoreWithMockedScripts()

    scripts.store.save(operation=Operation(trace_id="trace-1", status=status))

    assert (scripts.save_without_expiry.call_count, scripts.save_with_expiry.call_count) == (1, 0)
