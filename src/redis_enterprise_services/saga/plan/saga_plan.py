from redis_enterprise_services.exceptions.saga import InvalidPlanError
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep

KIND_RANK: dict[StepKind, int] = {StepKind.COMPENSATABLE: 0, StepKind.PIVOT: 1, StepKind.RETRIABLE: 2}


class SagaPlan:
    def __init__(self, *, steps: list[PreparableStep], lock_keys: list[str]) -> None:
        validate_plan(steps=steps, lock_keys=lock_keys)
        self.steps: list[PreparableStep] = list(steps)
        self.lock_keys: list[str] = list(lock_keys)


def validate_plan(*, steps: list[PreparableStep], lock_keys: list[str]) -> None:
    reject_empty_steps(steps=steps)
    reject_out_of_order_kinds(steps=steps)
    reject_second_pivot(steps=steps)
    reject_repeated_keys(steps=steps)
    reject_empty_lock_keys(lock_keys=lock_keys)


def reject_empty_steps(*, steps: list[PreparableStep]) -> None:
    if not steps:
        raise InvalidPlanError(message="a plan has at least one step")


def reject_out_of_order_kinds(*, steps: list[PreparableStep]) -> None:
    ranks: list[int] = [KIND_RANK[step.kind] for step in steps]
    if ranks != sorted(ranks):
        raise InvalidPlanError(message=f"steps out of order: {[step.kind.value for step in steps]}")


def reject_second_pivot(*, steps: list[PreparableStep]) -> None:
    if [step.kind for step in steps].count(StepKind.PIVOT) > 1:
        raise InvalidPlanError(message="a plan has at most one pivot step")


def reject_repeated_keys(*, steps: list[PreparableStep]) -> None:
    keys: list[str] = [step.key for step in steps]
    if len(set(keys)) != len(keys):
        raise InvalidPlanError(message=f"step keys repeat: {keys}")


def reject_empty_lock_keys(*, lock_keys: list[str]) -> None:
    if not lock_keys:
        raise InvalidPlanError(message="a plan locks at least one database")
