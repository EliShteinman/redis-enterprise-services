from collections.abc import Callable

from pydantic import BaseModel, JsonValue

from redis_enterprise_services.exceptions.saga import StepNotPreparedError
from redis_enterprise_services.saga.context import SagaContext
from redis_enterprise_services.saga.kind import StepKind
from redis_enterprise_services.saga.models import ObtainedBy
from redis_enterprise_services.saga.runnable import OnKept, RunnableStep
from redis_enterprise_services.saga.saga_step import SagaStep

type BuildInput[TInput] = Callable[[SagaContext], TInput]


class PlannedStep[TInput: BaseModel, TResult: BaseModel](RunnableStep):
    def __init__(self, *, key: str, step: SagaStep[TInput, TResult], build_input: BuildInput[TInput]) -> None:
        self._key: str = key
        self._step: SagaStep[TInput, TResult] = step
        self._build_input: BuildInput[TInput] = build_input
        self._context: SagaContext | None = None
        self._input: TInput | None = None
        self._result: TResult | None = None
        self._obtained_by: ObtainedBy | None = None

    @property
    def key(self) -> str:
        return self._key

    @property
    def kind(self) -> StepKind:
        return self._step.kind

    @property
    def has_result(self) -> bool:
        return self._result is not None

    @property
    def obtained_by(self) -> ObtainedBy | None:
        return self._obtained_by

    def prepare(self, *, context: SagaContext) -> JsonValue:
        self._context = context
        self._input = self._build_input(context)
        return self._input.model_dump(mode="json")

    def execute(self, *, on_kept: OnKept) -> None:
        self._step.execute(
            step_input=self._prepared_input(),
            keep_result=lambda result: self._keep(
                result=result, obtained_by=ObtainedBy.KEPT, on_kept=on_kept
            ),
        )

    def resolve(self, *, on_kept: OnKept) -> bool:
        found: TResult | None = self._step.find_outcome(step_input=self._prepared_input(), kept=self._result)
        if found is None:
            return False
        self._keep(result=found, obtained_by=ObtainedBy.FOUND, on_kept=on_kept)
        return True

    def compensate(self) -> None:
        if self._result is None:
            return
        self._step.compensate(step_input=self._prepared_input(), result=self._result)

    def _keep(self, *, result: TResult, obtained_by: ObtainedBy, on_kept: OnKept) -> None:
        if self._result is not None:
            return
        self._result = result
        self._obtained_by = obtained_by
        if self._context is not None:
            self._context.keep(key=self._key, result=result)
        on_kept(result.model_dump(mode="json"), obtained_by)

    def _prepared_input(self) -> TInput:
        if self._input is None:
            raise StepNotPreparedError(message=f"step {self._key} ran before its input was built")
        return self._input
