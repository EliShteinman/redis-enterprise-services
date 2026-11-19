from typing import Protocol

from pydantic import BaseModel

from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.saga.plan.prepared_saga_step import PreparedSagaStep
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep, PreparedStep
from redis_enterprise_services.saga.plan.step_results import StepResults


class BuildInput[TInput](Protocol):
    def __call__(self, *, step_results: StepResults) -> TInput: ...


class PlannedStep[TInput: BaseModel, TResult: BaseModel](PreparableStep):
    def __init__(self, *, key: str, step: SagaStep[TInput, TResult], build_input: BuildInput[TInput]) -> None:
        self._key: str = key
        self._step: SagaStep[TInput, TResult] = step
        self._build_input: BuildInput[TInput] = build_input

    @property
    def key(self) -> str:
        return self._key

    @property
    def kind(self) -> StepKind:
        return self._step.kind

    def prepare(self, *, step_results: StepResults) -> PreparedStep:
        return PreparedSagaStep(
            key=self._key,
            step=self._step,
            step_input=self._build_input(step_results=step_results),
            step_results=step_results,
        )
