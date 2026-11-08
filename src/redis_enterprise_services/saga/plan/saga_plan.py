from redis_enterprise_services.exceptions.saga import InvalidPlanError
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep

KIND_RANK: dict[StepKind, int] = {StepKind.COMPENSATABLE: 0, StepKind.PIVOT: 1, StepKind.RETRIABLE: 2}


class SagaPlan:
    def __init__(self, *, steps: list[PreparableStep], lock_keys: list[str]) -> None:
        if not steps:
            raise InvalidPlanError(message="a plan has at least one step")
        validate_steps(steps=steps)
        if not lock_keys:
            raise InvalidPlanError(message="a plan locks at least one database")
        self.steps: list[PreparableStep] = list(steps)
        self.lock_keys: list[str] = list(lock_keys)


def validate_steps(*, steps: list[PreparableStep]) -> None:
    ranks: list[int] = [KIND_RANK[step.kind] for step in steps]
    if ranks != sorted(ranks):
        raise InvalidPlanError(message=f"steps out of order: {[step.kind.value for step in steps]}")
    if ranks.count(KIND_RANK[StepKind.PIVOT]) > 1:
        raise InvalidPlanError(message="a plan has at most one pivot step")
    keys: list[str] = [step.key for step in steps]
    if len(set(keys)) != len(keys):
        raise InvalidPlanError(message=f"step keys repeat: {keys}")
