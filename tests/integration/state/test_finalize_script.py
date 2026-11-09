from collections.abc import Callable
from typing import cast

import pytest
from redis import Redis

from redis_enterprise_services.config.settings import Settings
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.public_error import PublicError
from redis_enterprise_services.recovery.finalize_abandoned_result import FinalizeAbandonedResult
from redis_enterprise_services.recovery.stored_saga import StoredSaga
from redis_enterprise_services.saga.contract.saga_record import SagaRecord, SagaStatus
from redis_enterprise_services.state.redis_abandoned_store import RedisAbandonedStore
from redis_enterprise_services.state.redis_keys import RedisKeys

ERROR: PublicError = PublicError(code="internal_error", message="the pod stopped")


class AbandonedTrace:
    def __init__(
        self, *, client: Redis, keys: RedisKeys, trace_id: str, lock_key: str, saga_status: SagaStatus
    ) -> None:
        self.client: Redis = client
        self.keys: RedisKeys = keys
        self.trace_id: str = trace_id
        self.lock_key: str = keys.lock(lock_key=lock_key)
        self.saga: StoredSaga = StoredSaga(
            raw_json=SagaRecord(saga_id=trace_id, status=saga_status, steps=[]).model_dump_json(), record=None
        )
        client.set(
            keys.operation(trace_id=trace_id),
            self.operation(status=OperationStatus.RUNNING).model_dump_json(),
        )
        client.sadd(keys.open_trace_ids(), trace_id)
        client.set(keys.saga_record(saga_id=trace_id), self.saga.raw_json)
        client.set(self.lock_key, trace_id)
        client.sadd(keys.held_locks(owner=trace_id), self.lock_key)

    def operation(self, *, status: OperationStatus) -> Operation:
        error: PublicError | None = None if status is OperationStatus.RUNNING else ERROR
        return Operation(trace_id=self.trace_id, status=status, error=error)

    def stored_operation(self) -> Operation:
        return Operation.model_validate_json(
            json_data=cast(str, self.client.get(self.keys.operation(trace_id=self.trace_id)))
        )

    def is_open(self) -> bool:
        return bool(self.client.sismember(self.keys.open_trace_ids(), self.trace_id))


@pytest.fixture
def store(client: Redis, keys: RedisKeys, settings: Settings) -> RedisAbandonedStore:
    return RedisAbandonedStore(
        client=client, keys=keys, finished_ttl_seconds=settings.state.finished_ttl_seconds
    )


@pytest.fixture
def abandoned(
    client: Redis, keys: RedisKeys, trace_id: str, lock_keys: list[str]
) -> Callable[[SagaStatus], AbandonedTrace]:
    return lambda saga_status: AbandonedTrace(
        client=client, keys=keys, trace_id=trace_id, lock_key=lock_keys[0], saga_status=saga_status
    )


def finalize(
    store: RedisAbandonedStore,
    trace: AbandonedTrace,
    *,
    status: OperationStatus,
    release_locks: bool,
    interrupted_saga: SagaRecord | None = None,
) -> FinalizeAbandonedResult:
    return store.finalize_if_still_abandoned(
        operation=trace.operation(status=status),
        expected_saga=trace.saga,
        interrupted_saga=interrupted_saga,
        release_locks=release_locks,
    )


def test_a_cleanly_ended_saga_frees_its_locks(
    client: Redis,
    keys: RedisKeys,
    trace_id: str,
    store: RedisAbandonedStore,
    abandoned: Callable[[SagaStatus], AbandonedTrace],
) -> None:
    trace: AbandonedTrace = abandoned(SagaStatus.SUCCEEDED)

    finalize(store, trace, status=OperationStatus.REQUIRES_MANUAL_INTERVENTION, release_locks=True)

    assert not client.exists(trace.lock_key)


def test_a_saga_that_needs_manual_intervention_keeps_its_locks(
    client: Redis,
    keys: RedisKeys,
    trace_id: str,
    store: RedisAbandonedStore,
    abandoned: Callable[[SagaStatus], AbandonedTrace],
) -> None:
    trace: AbandonedTrace = abandoned(SagaStatus.RUNNING)

    finalize(store, trace, status=OperationStatus.REQUIRES_MANUAL_INTERVENTION, release_locks=False)

    assert client.get(trace.lock_key) == trace_id


def test_a_manual_operation_stays_open_without_expiry(
    client: Redis,
    keys: RedisKeys,
    trace_id: str,
    store: RedisAbandonedStore,
    abandoned: Callable[[SagaStatus], AbandonedTrace],
) -> None:
    trace: AbandonedTrace = abandoned(SagaStatus.RUNNING)

    finalize(store, trace, status=OperationStatus.REQUIRES_MANUAL_INTERVENTION, release_locks=False)

    assert (trace.is_open(), client.ttl(keys.operation(trace_id=trace_id))) == (True, -1)


def test_a_rolled_back_operation_expires_and_leaves_the_open_set(
    client: Redis,
    keys: RedisKeys,
    trace_id: str,
    store: RedisAbandonedStore,
    abandoned: Callable[[SagaStatus], AbandonedTrace],
) -> None:
    trace: AbandonedTrace = abandoned(SagaStatus.ROLLED_BACK)

    finalize(store, trace, status=OperationStatus.ROLLED_BACK, release_locks=True)

    assert (trace.is_open(), client.ttl(keys.operation(trace_id=trace_id)) > 0) == (False, True)


def test_an_operation_with_a_heartbeat_is_not_finalized(
    client: Redis,
    keys: RedisKeys,
    trace_id: str,
    store: RedisAbandonedStore,
    abandoned: Callable[[SagaStatus], AbandonedTrace],
) -> None:
    trace: AbandonedTrace = abandoned(SagaStatus.RUNNING)
    client.set(keys.heartbeat(trace_id=trace_id), "alive")

    finalize(store, trace, status=OperationStatus.REQUIRES_MANUAL_INTERVENTION, release_locks=False)

    assert trace.stored_operation().status is OperationStatus.RUNNING


def test_a_saga_record_that_changed_since_it_was_read_is_not_overwritten(
    client: Redis,
    keys: RedisKeys,
    trace_id: str,
    store: RedisAbandonedStore,
    abandoned: Callable[[SagaStatus], AbandonedTrace],
) -> None:
    trace: AbandonedTrace = abandoned(SagaStatus.RUNNING)
    changed: SagaRecord = SagaRecord(
        saga_id=trace_id, status=SagaStatus.REQUIRES_MANUAL_INTERVENTION, steps=[]
    )
    client.set(keys.saga_record(saga_id=trace_id), changed.model_dump_json())

    result: FinalizeAbandonedResult = finalize(
        store, trace, status=OperationStatus.REQUIRES_MANUAL_INTERVENTION, release_locks=False
    )

    assert result is FinalizeAbandonedResult.SAGA_CHANGED


def test_an_open_trace_without_an_operation_record_leaves_the_open_set(
    client: Redis,
    keys: RedisKeys,
    trace_id: str,
    store: RedisAbandonedStore,
    abandoned: Callable[[SagaStatus], AbandonedTrace],
) -> None:
    trace: AbandonedTrace = abandoned(SagaStatus.RUNNING)
    client.delete(keys.operation(trace_id=trace_id))

    finalize(store, trace, status=OperationStatus.REQUIRES_MANUAL_INTERVENTION, release_locks=False)

    assert not trace.is_open()


def test_an_interrupted_saga_is_stored_as_its_interrupted_copy(
    client: Redis,
    keys: RedisKeys,
    trace_id: str,
    store: RedisAbandonedStore,
    abandoned: Callable[[SagaStatus], AbandonedTrace],
) -> None:
    trace: AbandonedTrace = abandoned(SagaStatus.RUNNING)
    interrupted: SagaRecord = SagaRecord(
        saga_id=trace_id, status=SagaStatus.RUNNING, steps=[]
    ).interrupted_copy()

    finalize(
        store,
        trace,
        status=OperationStatus.REQUIRES_MANUAL_INTERVENTION,
        release_locks=False,
        interrupted_saga=interrupted,
    )

    assert client.get(keys.saga_record(saga_id=trace_id)) == interrupted.model_dump_json()


def test_releasing_leaves_a_lock_that_another_owner_took(
    client: Redis,
    keys: RedisKeys,
    trace_id: str,
    store: RedisAbandonedStore,
    abandoned: Callable[[SagaStatus], AbandonedTrace],
) -> None:
    trace: AbandonedTrace = abandoned(SagaStatus.SUCCEEDED)
    client.set(trace.lock_key, "itest-other-owner")

    finalize(store, trace, status=OperationStatus.REQUIRES_MANUAL_INTERVENTION, release_locks=True)

    assert client.get(trace.lock_key) == "itest-other-owner"
