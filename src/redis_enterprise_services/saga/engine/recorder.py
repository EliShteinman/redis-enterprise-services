from pydantic import JsonValue

from redis_enterprise_services.saga.contract.models import ObtainedBy, SagaRecord, StepRecord, StepStatus
from redis_enterprise_services.saga.contract.state import SagaStateRepository


class StepRecorder:
    def __init__(self, *, state: SagaStateRepository, record: SagaRecord, step: StepRecord) -> None:
        self._state: SagaStateRepository = state
        self._record: SagaRecord = record
        self._step: StepRecord = step

    def started(self, *, step_input: JsonValue) -> None:
        self._step.step_input = step_input
        self._mark(status=StepStatus.RUNNING)

    def kept(self, *, result: JsonValue, obtained_by: ObtainedBy) -> None:
        self._step.result = result
        self._step.obtained_by = obtained_by
        self._state.save(record=self._record)

    def failed_attempt(self, *, error: str) -> None:
        self._step.error = error
        self._state.save(record=self._record)

    def done(self) -> None:
        self._step.error = None
        self._mark(status=StepStatus.DONE)

    def failed(self) -> None:
        self._mark(status=StepStatus.FAILED)

    def unresolved(self) -> None:
        self._mark(status=StepStatus.UNRESOLVED)

    def compensating(self) -> None:
        self._mark(status=StepStatus.COMPENSATING)

    def compensated(self) -> None:
        self._mark(status=StepStatus.COMPENSATED)

    def compensation_failed(self, *, error: str) -> None:
        self._step.error = error
        self._mark(status=StepStatus.COMPENSATION_FAILED)

    def _mark(self, *, status: StepStatus) -> None:
        self._step.status = status
        self._state.save(record=self._record)
