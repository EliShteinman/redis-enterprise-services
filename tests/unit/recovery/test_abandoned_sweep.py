from unittest.mock import MagicMock, create_autospec

import pytest

from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.recovery.abandoned_store import AbandonedStore
from redis_enterprise_services.recovery.abandoned_sweep import AbandonedSweep
from redis_enterprise_services.recovery.mark_abandoned_result import MarkAbandonedResult
from redis_enterprise_services.recovery.stored_saga import StoredSaga
from redis_enterprise_services.saga.contract.saga_record import SagaRecord, SagaStatus, StepRecord, StepStatus
from redis_enterprise_services.saga.contract.step_kind import StepKind


class SweepHarness:
    def __init__(self, *, saga: SagaRecord | None) -> None:
        self.store: MagicMock = create_autospec(spec=AbandonedStore, instance=True)
        self.store.open_trace_ids_without_heartbeat.return_value = ["trace-1"]
        self.store.find_saga.return_value = (
            None if saga is None else StoredSaga(raw_json=saga.model_dump_json(), record=saga)
        )
        self.store.mark_abandoned.return_value = MarkAbandonedResult.MARKED
        AbandonedSweep(
            store=self.store,
            public_errors=PublicErrors(
                settings=OperationSettings(
                    public_code_by_error_code={}, cluster_caused_public_codes=frozenset()
                ),
                internal_error_message="internal error",
            ),
        ).sweep()

    def marked_arguments(self) -> tuple[Operation, SagaRecord | None]:
        kwargs: dict[str, object] = self.store.mark_abandoned.call_args.kwargs
        operation: object = kwargs["operation"]
        saga: object = kwargs["interrupted_saga"]
        assert isinstance(operation, Operation)
        assert saga is None or isinstance(saga, SagaRecord)
        return operation, saga


def saga_record(*, status: SagaStatus) -> SagaRecord:
    return SagaRecord(
        saga_id="trace-1",
        status=status,
        steps=[StepRecord(key="database", kind=StepKind.COMPENSATABLE, status=StepStatus.RUNNING)],
    )


def test_an_operation_whose_saga_never_started_is_rejected() -> None:
    operation, interrupted_saga = SweepHarness(saga=None).marked_arguments()

    assert (operation.status, interrupted_saga) == (OperationStatus.REJECTED, None)


def test_a_running_saga_is_stopped_for_manual_intervention() -> None:
    operation, interrupted_saga = SweepHarness(saga=saga_record(status=SagaStatus.RUNNING)).marked_arguments()

    assert interrupted_saga is not None
    assert (operation.status, interrupted_saga.status, interrupted_saga.steps[0].status) == (
        OperationStatus.REQUIRES_MANUAL_INTERVENTION,
        SagaStatus.REQUIRES_MANUAL_INTERVENTION,
        StepStatus.UNRESOLVED,
    )


@pytest.mark.parametrize(
    argnames=("saga_status", "operation_status"),
    argvalues=[
        (SagaStatus.SUCCEEDED, OperationStatus.REQUIRES_MANUAL_INTERVENTION),
        (SagaStatus.ROLLED_BACK, OperationStatus.ROLLED_BACK),
        (SagaStatus.REQUIRES_MANUAL_INTERVENTION, OperationStatus.REQUIRES_MANUAL_INTERVENTION),
    ],
)
def test_an_ended_saga_record_is_not_rewritten(
    saga_status: SagaStatus, operation_status: OperationStatus
) -> None:
    operation, interrupted_saga = SweepHarness(saga=saga_record(status=saga_status)).marked_arguments()

    assert (operation.status, interrupted_saga) == (operation_status, None)


def test_an_operation_whose_saga_rolled_back_lists_nothing_left_behind() -> None:
    operation, _ = SweepHarness(saga=saga_record(status=SagaStatus.ROLLED_BACK)).marked_arguments()

    assert operation.not_rolled_back == []


def test_an_unreadable_saga_does_not_stop_the_sweep() -> None:
    store: MagicMock = create_autospec(spec=AbandonedStore, instance=True)
    store.open_trace_ids_without_heartbeat.return_value = ["trace-bad", "trace-good"]

    def find_saga(*, trace_id: str) -> StoredSaga | None:
        if trace_id == "trace-bad":
            SagaRecord.model_validate_json(json_data="{}")
        return None

    store.find_saga.side_effect = find_saga
    store.mark_abandoned.return_value = MarkAbandonedResult.MARKED

    AbandonedSweep(
        store=store,
        public_errors=PublicErrors(
            settings=OperationSettings(public_code_by_error_code={}, cluster_caused_public_codes=frozenset()),
            internal_error_message="internal error",
        ),
    ).sweep()

    assert [call.kwargs["operation"].trace_id for call in store.mark_abandoned.call_args_list] == [
        "trace-good"
    ]
