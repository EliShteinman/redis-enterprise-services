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
    def __init__(
        self, *, record_writer: SagaRecordWriter, record: SagaRecord, step_record: StepRecord
    ) -> None:
        self._record_writer: SagaRecordWriter = record_writer
        self._record: SagaRecord = record
        self._step_record: StepRecord = step_record

    def started(self, *, step_input: JsonValue) -> None:
        self._step_record.step_input = step_input
        self._mark(status=StepStatus.RUNNING)

    def result_kept(self, *, result: JsonValue, obtained_by: ObtainedBy) -> None:
        self._step_record.result = result
        self._step_record.obtained_by = obtained_by
        self._record_writer.save(record=self._record)

    def result_forgotten(self) -> None:
        self._step_record.result = None
        self._step_record.obtained_by = None
        self._record_writer.save(record=self._record)

    def attempt_failed(self, *, error: StepError) -> None:
        self._step_record.error = error
        self._record_writer.save(record=self._record)

    def done(self) -> None:
        self._step_record.error = None
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
        self._step_record.compensation_error = error
        self._mark(status=StepStatus.COMPENSATION_FAILED)

    def _mark(self, *, status: StepStatus) -> None:
        self._step_record.status = status
        self._record_writer.save(record=self._record)
