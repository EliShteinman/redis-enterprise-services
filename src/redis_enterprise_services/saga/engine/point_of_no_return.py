from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.saga.engine.step_runner import StepOutcome
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep


def has_passed_point_of_no_return(*, steps_before: list[PreparableStep]) -> bool:
    return any(step.kind is not StepKind.COMPENSATABLE for step in steps_before)


def compensation_allowed(*, outcome: StepOutcome, passed_point_of_no_return: bool) -> bool:
    return outcome is not StepOutcome.REQUIRES_MANUAL_INTERVENTION and not passed_point_of_no_return
