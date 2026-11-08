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

    def mark_running(self, *, step_input: JsonValue) -> None:
        self._step_record.step_input = step_input
        self._save_status(status=StepStatus.RUNNING)

    def save_result(self, *, result: JsonValue, obtained_by: ObtainedBy) -> None:
        self._step_record.result = result
        self._step_record.obtained_by = obtained_by
        self._record_writer.save(record=self._record)

    def clear_saved_result(self) -> None:
        self._step_record.result = None
        self._step_record.obtained_by = None
        self._record_writer.save(record=self._record)

    def save_error(self, *, error: StepError) -> None:
        self._step_record.error = error
        self._record_writer.save(record=self._record)

    def mark_done(self) -> None:
        self._step_record.error = None
        self._save_status(status=StepStatus.DONE)

    def mark_failed(self) -> None:
        self._save_status(status=StepStatus.FAILED)

    def mark_unresolved(self) -> None:
        self._save_status(status=StepStatus.UNRESOLVED)

    def mark_compensating(self) -> None:
        self._save_status(status=StepStatus.COMPENSATING)

    def mark_compensated(self) -> None:
        self._save_status(status=StepStatus.COMPENSATED)

    def mark_compensation_failed(self, *, error: StepError) -> None:
        self._step_record.compensation_error = error
        self._save_status(status=StepStatus.COMPENSATION_FAILED)

    def _save_status(self, *, status: StepStatus) -> None:
        self._step_record.status = status
        self._record_writer.save(record=self._record)
