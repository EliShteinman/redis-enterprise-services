from pydantic import BaseModel, JsonValue

from redis_enterprise_services.saga.contract.saga_record import ObtainedBy
from redis_enterprise_services.saga.contract.saga_step import SagaStep
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.saga.plan.step_protocols import OnResultKept, PreparedStep
from redis_enterprise_services.saga.plan.step_results import StepResults


class PreparedSagaStep[TInput: BaseModel, TResult: BaseModel](PreparedStep):
    def __init__(
        self, *, key: str, step: SagaStep[TInput, TResult], step_input: TInput, step_results: StepResults
    ) -> None:
        self._key: str = key
        self._step: SagaStep[TInput, TResult] = step
        self._step_input: TInput = step_input
        self._step_results: StepResults = step_results
        self._result: TResult | None = None
        self._obtained_by: ObtainedBy | None = None

    @property
    def key(self) -> str:
        return self._key

    @property
    def kind(self) -> StepKind:
        return self._step.kind

    @property
    def step_input(self) -> JsonValue:
        return self._step_input.model_dump(mode="json")

    @property
    def has_result(self) -> bool:
        return self._result is not None

    @property
    def obtained_by(self) -> ObtainedBy | None:
        return self._obtained_by

    def execute(self, *, on_result_kept: OnResultKept) -> None:
        self._step.execute(
            step_input=self._step_input,
            keep_result=lambda result: self._keep_if_none_kept(
                result=result, obtained_by=ObtainedBy.KEPT, on_result_kept=on_result_kept
            ),
        )

    def find_outcome(self, *, on_result_kept: OnResultKept) -> bool:
        found: TResult | None = self._step.find_outcome(
            step_input=self._step_input,
            kept_result=self._result,
            keep_found_result=lambda result: self._keep_if_none_kept(
                result=result, obtained_by=ObtainedBy.FOUND, on_result_kept=on_result_kept
            ),
        )
        if found is None:
            return False
        self._keep_if_none_kept(result=found, obtained_by=ObtainedBy.FOUND, on_result_kept=on_result_kept)
        return True

    def compensate(self) -> None:
        if self._result is not None:
            self._step.compensate(step_input=self._step_input, result=self._result)

    def forget_result(self) -> None:
        self._result = None
        self._obtained_by = None
        self._step_results.forget(key=self._key)

    def _keep_if_none_kept(
        self, *, result: TResult, obtained_by: ObtainedBy, on_result_kept: OnResultKept
    ) -> None:
        if self._result is not None:
            return
        self._result = result
        self._obtained_by = obtained_by
        self._step_results.keep(key=self._key, result=result)
        on_result_kept(result=result.model_dump(mode="json"), obtained_by=obtained_by)
