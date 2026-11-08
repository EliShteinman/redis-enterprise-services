from typing import Protocol

from pydantic import BaseModel

from redis_enterprise_services.saga.contract.keep_result import KeepResult
from redis_enterprise_services.saga.contract.step_kind import StepKind


class SagaStep[TInput: BaseModel, TResult: BaseModel](Protocol):
    @property
    def kind(self) -> StepKind: ...

    def execute(self, *, step_input: TInput, keep_result: KeepResult[TResult]) -> None: ...

    def find_outcome(
        self, *, step_input: TInput, kept: TResult | None, keep_found: KeepResult[TResult]
    ) -> TResult | None: ...

    def compensate(self, *, step_input: TInput, result: TResult) -> None: ...
