from unittest.mock import MagicMock, create_autospec

import pytest

from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.operation_status import OperationStatus
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.recovery.abandoned_store import AbandonedStore
from redis_enterprise_services.recovery.abandoned_sweep import AbandonedSweep
from redis_enterprise_services.saga.contract.kind import StepKind
from redis_enterprise_services.saga.contract.models import SagaRecord, SagaStatus, StepRecord, StepStatus
from redis_enterprise_services.saga.contract.state import SagaRecordReader


class Sweep:
    def __init__(self, *, saga: SagaRecord | None) -> None:
        self.store: MagicMock = create_autospec(spec=AbandonedStore, instance=True)
        self.store.without_heartbeat.return_value = ["trace-1"]
        records: MagicMock = create_autospec(spec=SagaRecordReader, instance=True)
        records.find.return_value = saga
        AbandonedSweep(
            store=self.store,
            records=records,
            errors=PublicErrors(
                settings=OperationSettings(public_error_codes={}, cluster_error_codes=frozenset()),
                internal_error_message="internal error",
            ),
        ).sweep()

    def marked(self) -> tuple[Operation, SagaRecord | None]:
        kwargs: dict[str, object] = self.store.mark_abandoned.call_args.kwargs
        operation: object = kwargs["operation"]
        saga: object = kwargs["stopped_saga"]
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
    operation, saga = Sweep(saga=None).marked()

    assert (operation.status, saga) == (OperationStatus.REJECTED, None)


def test_a_running_saga_is_stopped_for_manual_intervention() -> None:
    operation, saga = Sweep(saga=saga_record(status=SagaStatus.RUNNING)).marked()

    assert saga is not None
    assert (operation.status, saga.status, saga.steps[0].status) == (
        OperationStatus.REQUIRES_MANUAL_INTERVENTION,
        SagaStatus.REQUIRES_MANUAL_INTERVENTION,
        StepStatus.UNRESOLVED,
    )


@pytest.mark.parametrize(argnames="status", argvalues=[SagaStatus.SUCCEEDED, SagaStatus.ROLLED_BACK])
def test_an_ended_saga_is_left_as_it_is(status: SagaStatus) -> None:
    operation, saga = Sweep(saga=saga_record(status=status)).marked()

    assert (operation.status, saga) == (OperationStatus.REQUIRES_MANUAL_INTERVENTION, None)
