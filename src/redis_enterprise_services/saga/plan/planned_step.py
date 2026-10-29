from typing import Protocol

from pydantic import BaseModel

from redis_enterprise_services.saga.contract.kind import StepKind
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.plan.context import SagaContext
from redis_enterprise_services.saga.plan.prepared_step import PreparedPlannedStep
from redis_enterprise_services.saga.plan.runnable import PreparedStep, RunnableStep


class BuildInput[TInput](Protocol):
    def __call__(self, *, context: SagaContext) -> TInput: ...


class PlannedStep[TInput: BaseModel, TResult: BaseModel](RunnableStep):
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

    def prepare(self, *, context: SagaContext) -> PreparedStep:
        return PreparedPlannedStep(
            key=self._key, step=self._step, step_input=self._build_input(context=context), context=context
        )
