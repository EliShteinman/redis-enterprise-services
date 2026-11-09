from enum import StrEnum
from typing import Self

from pydantic import BaseModel, JsonValue, ValidationError

from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.saga import MissingStepRecordError
from redis_enterprise_services.saga.contract.step_kind import StepKind


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


CLEANLY_ENDED_STATUSES: frozenset[SagaStatus] = frozenset({SagaStatus.SUCCEEDED, SagaStatus.ROLLED_BACK})


NOT_ROLLED_BACK_STEP_STATUSES: frozenset[StepStatus] = frozenset(
    {StepStatus.DONE, StepStatus.UNRESOLVED, StepStatus.COMPENSATING, StepStatus.COMPENSATION_FAILED}
)


class ObtainedBy(StrEnum):
    KEPT = "kept"
    FOUND = "found"


class StepError(BaseModel):
    code: str
    message: str
    remote_code: str | None = None

    @classmethod
    def from_exception(cls, *, error: RedisEnterpriseServicesError) -> Self:
        return cls(code=error.code, message=error.message, remote_code=error.cluster_error_code)

    @classmethod
    def from_input_validation_error(cls, *, error: ValidationError) -> Self:
        return cls(code=RedisEnterpriseServicesError.code, message=f"cannot build the input: {error}")


class StepRecord(BaseModel):
    key: str
    kind: StepKind
    status: StepStatus = StepStatus.PENDING
    step_input: JsonValue = None
    result: JsonValue = None
    obtained_by: ObtainedBy | None = None
    error: StepError | None = None
    compensation_error: StepError | None = None

    def last_error(self) -> StepError | None:
        return self.compensation_error or self.error


class SagaRecord(BaseModel):
    saga_id: str
    status: SagaStatus = SagaStatus.RUNNING
    steps: list[StepRecord]
    stopped_at: str | None = None

    def step(self, *, key: str) -> StepRecord:
        for step in self.steps:
            if step.key == key:
                return step
        raise MissingStepRecordError(message=f"saga {self.saga_id} has no step {key}")

    def stopped_step(self) -> StepRecord | None:
        return next((step for step in self.steps if step.key == self.stopped_at), None)

    def not_rolled_back_steps(self) -> list[StepRecord]:
        return [step for step in self.steps if step.status in NOT_ROLLED_BACK_STEP_STATUSES]

    def has_ended_cleanly(self) -> bool:
        return self.status in CLEANLY_ENDED_STATUSES

    def interrupted_copy(self) -> Self:
        interrupted: Self = self.model_copy(deep=True)
        interrupted.mark_interrupted()
        return interrupted

    def mark_interrupted(self) -> None:
        self.stopped_at = self.stopped_at or interrupted_step_key(steps=self.steps)
        self.status = SagaStatus.REQUIRES_MANUAL_INTERVENTION
        for step in self.steps:
            if step.status is StepStatus.RUNNING:
                step.status = StepStatus.UNRESOLVED


def interrupted_step_key(*, steps: list[StepRecord]) -> str | None:
    running_keys: list[str] = [step.key for step in steps if step.status is StepStatus.RUNNING]
    pending_keys: list[str] = [step.key for step in steps if step.status is StepStatus.PENDING]
    return next(iter(running_keys + pending_keys), None)
