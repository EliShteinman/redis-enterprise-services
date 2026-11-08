from unittest.mock import MagicMock, create_autospec

import pytest

from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.public_error import PublicError
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.recovery.abandoned_store import AbandonedStore
from redis_enterprise_services.recovery.abandoned_sweep import AbandonedSweep, operation_after_crash
from redis_enterprise_services.recovery.finalize_abandoned_result import FinalizeAbandonedResult
from redis_enterprise_services.recovery.stored_saga import StoredSaga
from redis_enterprise_services.saga.contract.saga_record import SagaRecord, SagaStatus, StepRecord, StepStatus
from redis_enterprise_services.saga.contract.step_kind import StepKind

INTERNAL_ERROR: PublicError = PublicError(code="internal_error", message="internal error")


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


def test_an_unreadable_saga_does_not_stop_the_sweep() -> None:
    store: MagicMock = create_autospec(spec=AbandonedStore, instance=True)
    store.abandoned_candidate_trace_ids.return_value = ["trace-bad", "trace-good"]

    def find_saga(*, trace_id: str) -> StoredSaga | None:
        if trace_id == "trace-bad":
            SagaRecord.model_validate_json(json_data="{}")
        return None

    store.find_saga.side_effect = find_saga
    store.finalize_if_still_abandoned.return_value = FinalizeAbandonedResult.FINALIZED

    AbandonedSweep(
        store=store,
        public_errors=PublicErrors(
            settings=OperationSettings(
                public_code_by_internal_code={}, public_codes_with_cluster_details=frozenset()
            ),
            internal_error_message="internal error",
        ),
    ).sweep()

    assert [
        call.kwargs["operation"].trace_id for call in store.finalize_if_still_abandoned.call_args_list
    ] == ["trace-good"]
