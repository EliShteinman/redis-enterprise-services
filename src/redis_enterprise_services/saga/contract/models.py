from enum import StrEnum
from typing import Self

from pydantic import BaseModel, JsonValue

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.saga.contract.kind import StepKind


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    UNRESOLVED = "unresolved"
    COMPENSATING = "compensating"
    COMPENSATED = "compensated"
    COMPENSATION_FAILED = "compensation_failed"


class SagaStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    ROLLED_BACK = "rolled_back"
    REQUIRES_MANUAL_INTERVENTION = "requires_manual_intervention"


SETTLED: frozenset[SagaStatus] = frozenset({SagaStatus.SUCCEEDED, SagaStatus.ROLLED_BACK})


class ObtainedBy(StrEnum):
    KEPT = "kept"
    FOUND = "found"


class StepError(BaseModel):
    code: str
    message: str
    remote_code: str | None = None

    @classmethod
    def of(cls, *, error: RedisEnterpriseServicesError) -> Self:
        return cls(code=error.code, message=error.message, remote_code=error.remote_code())


class StepRecord(BaseModel):
    key: str
    kind: StepKind
    status: StepStatus = StepStatus.PENDING
    step_input: JsonValue = None
    result: JsonValue = None
    obtained_by: ObtainedBy | None = None
    error: StepError | None = None
    compensation_error: StepError | None = None


class SagaRecord(BaseModel):
    saga_id: str
    status: SagaStatus = SagaStatus.RUNNING
    steps: list[StepRecord]
    stopped_at: str | None = None

    def stop_running(self) -> None:
        self.status = SagaStatus.REQUIRES_MANUAL_INTERVENTION
        for step in self.steps:
            if step.status is StepStatus.RUNNING:
                step.status = StepStatus.UNRESOLVED
                self.stopped_at = self.stopped_at or step.key
