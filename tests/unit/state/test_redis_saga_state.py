from unittest.mock import MagicMock, create_autospec

import pytest
from redis import Redis

from redis_enterprise_services.saga.contract.saga_record import SagaRecord, SagaStatus
from redis_enterprise_services.state.redis_keys import RedisKeys
from redis_enterprise_services.state.redis_saga_state import RedisSagaState


class Scripts:
    def __init__(self) -> None:
        self.unfinished: MagicMock = MagicMock()
        self.finished: MagicMock = MagicMock()
        client: MagicMock = create_autospec(spec=Redis, instance=True)
        client.register_script.side_effect = [self.unfinished, self.finished]
        self.state: RedisSagaState = RedisSagaState(
            client=client, keys=RedisKeys(prefix="res:", hash_tag="state"), finished_operation_ttl_seconds=600
        )


@pytest.mark.parametrize(
    argnames="status", argvalues=[SagaStatus.REQUIRES_MANUAL_INTERVENTION, SagaStatus.RUNNING]
)
def test_an_unsettled_saga_stays_unfinished_without_expiry(status: SagaStatus) -> None:
    scripts: Scripts = Scripts()

    scripts.state.save_final(record=SagaRecord(saga_id="trace-1", status=status, steps=[]))

    assert (scripts.unfinished.call_count, scripts.finished.call_count) == (1, 0)


def test_a_settled_saga_is_stored_with_the_expiry() -> None:
    scripts: Scripts = Scripts()

    scripts.state.save_final(record=SagaRecord(saga_id="trace-1", status=SagaStatus.SUCCEEDED, steps=[]))

    assert scripts.finished.call_args.kwargs["args"][2] == 600
