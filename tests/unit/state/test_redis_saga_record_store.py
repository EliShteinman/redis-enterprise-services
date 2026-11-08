from unittest.mock import MagicMock, create_autospec

import pytest
from redis import Redis

from redis_enterprise_services.saga.contract.saga_record import SagaRecord, SagaStatus
from redis_enterprise_services.state.redis_keys import RedisKeys
from redis_enterprise_services.state.redis_saga_record_store import RedisSagaRecordStore


class StoreWithMockedScripts:
    def __init__(self) -> None:
        self.save_without_expiry: MagicMock = MagicMock()
        self.save_with_expiry: MagicMock = MagicMock()
        client: MagicMock = create_autospec(spec=Redis, instance=True)
        client.register_script.side_effect = [self.save_without_expiry, self.save_with_expiry]
        self.store: RedisSagaRecordStore = RedisSagaRecordStore(
            client=client, keys=RedisKeys(key_prefix="res:", hash_tag="state"), finished_ttl_seconds=600
        )


@pytest.mark.parametrize(
    argnames="status", argvalues=[SagaStatus.REQUIRES_MANUAL_INTERVENTION, SagaStatus.RUNNING]
)
def test_a_saga_not_cleanly_ended_is_stored_without_expiry(status: SagaStatus) -> None:
    scripts: StoreWithMockedScripts = StoreWithMockedScripts()

    scripts.store.save_final(record=SagaRecord(saga_id="trace-1", status=status, steps=[]))

    assert (scripts.save_without_expiry.call_count, scripts.save_with_expiry.call_count) == (1, 0)


def test_a_cleanly_ended_saga_is_stored_with_the_expiry() -> None:
    scripts: StoreWithMockedScripts = StoreWithMockedScripts()

    scripts.store.save_final(record=SagaRecord(saga_id="trace-1", status=SagaStatus.SUCCEEDED, steps=[]))

    assert scripts.save_with_expiry.call_args.kwargs["args"][2] == 600
