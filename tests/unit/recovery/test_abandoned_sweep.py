import pytest

from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.public_error import PublicError
from redis_enterprise_services.recovery.abandoned_sweep import (
    interrupted_running_saga,
    locks_are_free_after_crash,
    operation_after_crash,
)
from redis_enterprise_services.recovery.stored_saga import StoredSaga
from redis_enterprise_services.saga.contract.saga_record import SagaRecord, SagaStatus, StepRecord, StepStatus
from redis_enterprise_services.saga.contract.step_kind import StepKind

INTERNAL_ERROR: PublicError = PublicError(
    code="internal_error", kind="needs_investigation", message="internal error"
)


def stored_saga(*, status: SagaStatus) -> StoredSaga:
    record: SagaRecord = SagaRecord(
        saga_id="trace-1",
        status=status,
        steps=[StepRecord(key="database", kind=StepKind.COMPENSATABLE, status=StepStatus.RUNNING)],
    )
    return StoredSaga(raw_json=record.model_dump_json(), record=record)


def test_an_operation_whose_saga_never_started_is_rejected() -> None:
    operation: Operation = operation_after_crash(trace_id="trace-1", saga=None, error=INTERNAL_ERROR)

    assert operation.status is OperationStatus.REJECTED


@pytest.mark.parametrize(
    argnames=("saga_status", "operation_status"),
    argvalues=[
        (SagaStatus.RUNNING, OperationStatus.REQUIRES_MANUAL_INTERVENTION),
        (SagaStatus.SUCCEEDED, OperationStatus.REQUIRES_MANUAL_INTERVENTION),
        (SagaStatus.ROLLED_BACK, OperationStatus.ROLLED_BACK),
        (SagaStatus.REQUIRES_MANUAL_INTERVENTION, OperationStatus.REQUIRES_MANUAL_INTERVENTION),
    ],
)
def test_the_saga_status_after_a_crash_sets_the_operation_status(
    saga_status: SagaStatus, operation_status: OperationStatus
) -> None:
    operation: Operation = operation_after_crash(
        trace_id="trace-1", saga=stored_saga(status=saga_status), error=INTERNAL_ERROR
    )

    assert operation.status is operation_status


def test_an_operation_whose_saga_rolled_back_lists_nothing_left_behind() -> None:
    operation: Operation = operation_after_crash(
        trace_id="trace-1", saga=stored_saga(status=SagaStatus.ROLLED_BACK), error=INTERNAL_ERROR
    )

    assert operation.not_rolled_back == []


@pytest.mark.parametrize(
    argnames=("saga_status", "interrupted"),
    argvalues=[
        (SagaStatus.RUNNING, True),
        (SagaStatus.SUCCEEDED, False),
        (SagaStatus.ROLLED_BACK, False),
        (SagaStatus.REQUIRES_MANUAL_INTERVENTION, False),
    ],
)
def test_only_a_running_saga_is_interrupted(saga_status: SagaStatus, interrupted: bool) -> None:
    assert (interrupted_running_saga(saga=stored_saga(status=saga_status)) is not None) is interrupted


def test_an_unreadable_saga_needs_manual_intervention() -> None:
    operation: Operation = operation_after_crash(
        trace_id="trace-1", saga=StoredSaga(raw_json="{}", record=None), error=INTERNAL_ERROR
    )

    assert operation.status is OperationStatus.REQUIRES_MANUAL_INTERVENTION


@pytest.mark.parametrize(
    argnames=("saga", "free"),
    argvalues=[
        pytest.param(None, True, id="never-started"),
        pytest.param(stored_saga(status=SagaStatus.SUCCEEDED), True, id="succeeded"),
        pytest.param(stored_saga(status=SagaStatus.ROLLED_BACK), True, id="rolled-back"),
        pytest.param(stored_saga(status=SagaStatus.RUNNING), False, id="running"),
        pytest.param(stored_saga(status=SagaStatus.REQUIRES_MANUAL_INTERVENTION), False, id="manual"),
        pytest.param(StoredSaga(raw_json="{}", record=None), False, id="unreadable"),
    ],
)
def test_the_locks_are_freed_after_a_crash_only_when_nothing_is_left_to_fix(
    saga: StoredSaga | None, free: bool
) -> None:
    assert locks_are_free_after_crash(saga=saga) is free
