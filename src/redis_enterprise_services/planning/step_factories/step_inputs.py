from typing import Protocol

from pydantic import BaseModel

from redis_enterprise_services.resources.models import CreatedResource
from redis_enterprise_services.saga.plan.step_results import StepResults


class UidFromStepResults(Protocol):
    def __call__(self, *, step_results: StepResults) -> int: ...


def fixed_input[TInput: BaseModel](*, step_results: StepResults, step_input: TInput) -> TInput:
    return step_input


def uid_created_by_step(*, step_results: StepResults, step_key: str) -> int:
    return step_results.result_of(key=step_key, result_type=CreatedResource).uid
