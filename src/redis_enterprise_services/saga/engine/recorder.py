from pydantic import JsonValue

from redis_enterprise_services.saga.contract.saga_record import (
    ObtainedBy,
    SagaRecord,
    StepError,
    StepRecord,
    StepStatus,
)
from redis_enterprise_services.saga.contract.saga_record_store import SagaRecordWriter


class StepRecorder:
    def __init__(self, *, records: SagaRecordWriter, record: SagaRecord, step: StepRecord) -> None:
        self._records: SagaRecordWriter = records
        self._record: SagaRecord = record
        self._step: StepRecord = step

    def started(self, *, step_input: JsonValue) -> None:
        self._step.step_input = step_input
        self._mark(status=StepStatus.RUNNING)

    def result_kept(self, *, result: JsonValue, obtained_by: ObtainedBy) -> None:
        self._step.result = result
        self._step.obtained_by = obtained_by
        self._records.save(record=self._record)

    def result_forgotten(self) -> None:
        self._step.result = None
        self._step.obtained_by = None
        self._records.save(record=self._record)

    def attempt_failed(self, *, error: StepError) -> None:
        self._step.error = error
        self._records.save(record=self._record)

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

    def compensation_failed(self, *, error: StepError) -> None:
        self._step.compensation_error = error
        self._mark(status=StepStatus.COMPENSATION_FAILED)

    def _mark(self, *, status: StepStatus) -> None:
        self._step.status = status
        self._records.save(record=self._record)
