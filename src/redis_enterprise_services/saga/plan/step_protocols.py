from typing import Protocol

from pydantic import JsonValue

from redis_enterprise_services.saga.contract.saga_record import ObtainedBy
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.saga.plan.saga_context import SagaContext


class OnResultKept(Protocol):
    def __call__(self, *, result: JsonValue, obtained_by: ObtainedBy) -> None: ...


class PreparedStep(Protocol):
    @property
    def key(self) -> str: ...

    @property
    def kind(self) -> StepKind: ...

    @property
    def step_input(self) -> JsonValue: ...

    @property
    def has_result(self) -> bool: ...

    @property
    def obtained_by(self) -> ObtainedBy | None: ...

    def execute(self, *, on_result_kept: OnResultKept) -> None: ...

    def find_outcome(self, *, on_result_kept: OnResultKept) -> bool: ...

    def compensate(self) -> None: ...

    def forget_result(self) -> None: ...


class PreparableStep(Protocol):
    @property
    def key(self) -> str: ...

    @property
    def kind(self) -> StepKind: ...

    def prepare(self, *, context: SagaContext) -> PreparedStep: ...
