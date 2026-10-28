from enum import StrEnum

from pydantic import BaseModel, JsonValue

from redis_enterprise_services.steps.kind import StepKind


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    UNRESOLVED = "unresolved"
    COMPENSATED = "compensated"
    COMPENSATION_FAILED = "compensation_failed"


class SagaStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    ROLLED_BACK = "rolled_back"
    REQUIRES_MANUAL_INTERVENTION = "requires_manual_intervention"


class ObtainedBy(StrEnum):
    KEPT = "kept"
    FOUND = "found"


class StepRecord(BaseModel):
    key: str
    kind: StepKind
    status: StepStatus = StepStatus.PENDING
    step_input: JsonValue = None
    result: JsonValue = None
    obtained_by: ObtainedBy | None = None
    error: str | None = None


class SagaRecord(BaseModel):
    saga_id: str
    status: SagaStatus = SagaStatus.RUNNING
    steps: list[StepRecord]
