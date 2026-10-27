from typing import Protocol

from pydantic import BaseModel

from redis_enterprise_services.steps.kind import StepKind
from redis_enterprise_services.steps.result import KeepResult


class SagaStep[TInput: BaseModel, TResult: BaseModel](Protocol):
    @property
    def kind(self) -> StepKind: ...

    def execute(self, *, step_input: TInput, keep_result: KeepResult[TResult]) -> None: ...

    def find_outcome(self, *, step_input: TInput, kept: TResult | None) -> TResult | None: ...

    def compensate(self, *, step_input: TInput, result: TResult) -> None: ...
