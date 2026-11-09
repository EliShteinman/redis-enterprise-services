import pytest

from redis_enterprise_services.saga.contract.saga_record import SagaRecord, SagaStatus, StepRecord, StepStatus
from redis_enterprise_services.saga.contract.step_kind import StepKind


def running_record() -> SagaRecord:
    return SagaRecord(
        saga_id="trace-1",
        steps=[
            StepRecord(key="database", kind=StepKind.COMPENSATABLE, status=StepStatus.DONE),
            StepRecord(key="acl", kind=StepKind.COMPENSATABLE, status=StepStatus.RUNNING),
            StepRecord(key="role", kind=StepKind.COMPENSATABLE),
        ],
    )


def test_an_interrupted_copy_needs_manual_intervention_and_stops_at_the_running_step() -> None:
    interrupted: SagaRecord = running_record().interrupted_copy()

    assert (interrupted.status, interrupted.stopped_at, interrupted.steps[1].status) == (
        SagaStatus.REQUIRES_MANUAL_INTERVENTION,
        "acl",
        StepStatus.UNRESOLVED,
    )


def test_an_interrupted_copy_leaves_the_original_record_unchanged() -> None:
    original: SagaRecord = running_record()

    original.interrupted_copy()

    assert original == running_record()


@pytest.mark.parametrize(
    argnames=("status", "left_behind"),
    argvalues=[
        (StepStatus.DONE, True),
        (StepStatus.UNRESOLVED, True),
        (StepStatus.COMPENSATING, True),
        (StepStatus.COMPENSATION_FAILED, True),
        (StepStatus.COMPENSATED, False),
        (StepStatus.FAILED, False),
        (StepStatus.PENDING, False),
    ],
)
def test_only_steps_whose_resource_may_remain_are_not_rolled_back(
    status: StepStatus, left_behind: bool
) -> None:
    record: SagaRecord = SagaRecord(
        saga_id="trace-1", steps=[StepRecord(key="database", kind=StepKind.COMPENSATABLE, status=status)]
    )

    assert bool(record.not_rolled_back_steps()) is left_behind
