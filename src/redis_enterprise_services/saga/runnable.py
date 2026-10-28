from collections.abc import Callable
from typing import Protocol

from pydantic import JsonValue

from redis_enterprise_services.saga.context import SagaContext
from redis_enterprise_services.saga.kind import StepKind
from redis_enterprise_services.saga.models import ObtainedBy

type OnKept = Callable[[JsonValue, ObtainedBy], None]


class RunnableStep(Protocol):
    @property
    def key(self) -> str: ...

    @property
    def kind(self) -> StepKind: ...

    @property
    def has_result(self) -> bool: ...

    @property
    def obtained_by(self) -> ObtainedBy | None: ...

    def prepare(self, *, context: SagaContext) -> JsonValue: ...

    def execute(self, *, on_kept: OnKept) -> None: ...

    def resolve(self, *, on_kept: OnKept) -> bool: ...

    def compensate(self) -> None: ...
