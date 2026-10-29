from typing import Protocol

from pydantic import JsonValue

from redis_enterprise_services.saga.contract.kind import StepKind
from redis_enterprise_services.saga.contract.models import ObtainedBy
from redis_enterprise_services.saga.plan.context import SagaContext


class OnKept(Protocol):
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

    def execute(self, *, on_kept: OnKept) -> None: ...

    def resolve(self, *, on_kept: OnKept) -> bool: ...

    def compensate(self) -> None: ...


class RunnableStep(Protocol):
    @property
    def key(self) -> str: ...

    @property
    def kind(self) -> StepKind: ...

    def prepare(self, *, context: SagaContext) -> PreparedStep: ...
