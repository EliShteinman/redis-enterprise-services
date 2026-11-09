from unittest.mock import MagicMock, create_autospec

import pytest
from redis import Redis

from redis_enterprise_services.saga.contract.saga_record import SagaRecord, SagaStatus
from redis_enterprise_services.state.redis_keys import RedisKeys
from redis_enterprise_services.state.redis_saga_record_store import RedisSagaRecordStore
from redis_enterprise_services.state.tracked_record_writer import TrackedRecordWriter


@pytest.mark.parametrize(
    argnames=("status", "ttl_seconds"),
    argvalues=[
        (SagaStatus.SUCCEEDED, 600),
        (SagaStatus.ROLLED_BACK, 600),
        (SagaStatus.REQUIRES_MANUAL_INTERVENTION, 0),
        (SagaStatus.RUNNING, 0),
    ],
)
def test_only_a_cleanly_ended_saga_is_stored_with_the_expiry(status: SagaStatus, ttl_seconds: int) -> None:
    record_writer: MagicMock = create_autospec(spec=TrackedRecordWriter, instance=True)
    store: RedisSagaRecordStore = RedisSagaRecordStore(
        client=create_autospec(spec=Redis, instance=True),
        keys=RedisKeys(key_prefix="res:", hash_tag="state"),
        record_writer=record_writer,
        finished_ttl_seconds=600,
    )

    store.save_final(record=SagaRecord(saga_id="trace-1", status=status, steps=[]))

    assert record_writer.save.call_args.kwargs["ttl_seconds"] == ttl_seconds
