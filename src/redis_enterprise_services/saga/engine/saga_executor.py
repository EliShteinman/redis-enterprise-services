import logging
from collections.abc import Callable, Generator
from contextlib import contextmanager

from redis_enterprise_services.saga.contract.saga_lock import SagaLock
from redis_enterprise_services.saga.contract.saga_record import SagaRecord, SagaStatus
from redis_enterprise_services.saga.contract.saga_record_store import SagaRecordWriter
from redis_enterprise_services.saga.engine.compensator import Compensator
from redis_enterprise_services.saga.engine.point_of_no_return import (
    compensation_allowed,
    has_passed_point_of_no_return,
)
from redis_enterprise_services.saga.engine.step_recorder import StepRecorder
from redis_enterprise_services.saga.engine.step_runner import StepOutcome, StepRunner
from redis_enterprise_services.saga.plan.new_saga_record import new_saga_record
from redis_enterprise_services.saga.plan.saga_plan import SagaPlan
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep, PreparedStep
from redis_enterprise_services.saga.plan.step_results import StepResults

logger: logging.Logger = logging.getLogger(name=__name__)


class SagaExecutor:
    def __init__(
        self,
        *,
        record_writer: SagaRecordWriter,
        lock: SagaLock,
        runner: StepRunner,
        compensator: Compensator,
    ) -> None:
        self._record_writer: SagaRecordWriter = record_writer
        self._lock: SagaLock = lock
        self._runner: StepRunner = runner
        self._compensator: Compensator = compensator

    def run(
        self, *, saga_id: str, plan: SagaPlan, check_before_start: Callable[[], None] = lambda: None
    ) -> SagaRecord:
        record: SagaRecord = self._start(saga_id=saga_id, plan=plan, check_before_start=check_before_start)
        self._run_to_end(record=record, plan=plan)
        return record

    def _start(self, *, saga_id: str, plan: SagaPlan, check_before_start: Callable[[], None]) -> SagaRecord:
        self._lock.acquire(lock_keys=plan.lock_keys, owner=saga_id)
        with self._lock_released_on_failure(lock_keys=plan.lock_keys, saga_id=saga_id):
            check_before_start()
            self._lock.raise_unless_held(lock_keys=plan.lock_keys, owner=saga_id)
            record: SagaRecord = new_saga_record(saga_id=saga_id, plan=plan)
            self._record_writer.save(record=record)
            return record

    @contextmanager
    def _lock_released_on_failure(self, *, lock_keys: list[str], saga_id: str) -> Generator[None]:
        try:
            yield
        except BaseException:
            logger.info(msg=f"saga {saga_id} did not start, {lock_keys} released")
            self._lock.release(lock_keys=lock_keys, owner=saga_id)
            raise

    def _run_to_end(self, *, record: SagaRecord, plan: SagaPlan) -> None:
        try:
            record.status = self._run_steps(plan=plan, record=record)
        except BaseException:
            logger.error(msg=f"saga {record.saga_id} stopped on an unexpected error", exc_info=True)
            record.mark_interrupted()
            raise
        finally:
            self._end(record=record, plan=plan)

    def _run_steps(self, *, plan: SagaPlan, record: SagaRecord) -> SagaStatus:
        step_results: StepResults = StepResults()
        prepared_steps: list[tuple[PreparedStep, StepRecorder]] = []
        for position, (step, step_record) in enumerate(zip(plan.steps, record.steps, strict=True)):
            recorder: StepRecorder = StepRecorder(
                record_writer=self._record_writer, record=record, step_record=step_record
            )
            outcome, prepared = self._run_step(step=step, step_results=step_results, recorder=recorder)
            if prepared is not None:
                prepared_steps.append((prepared, recorder))
            if outcome is StepOutcome.DONE:
                continue
            record.stopped_at = step.key
            return self._status_after_stop(
                outcome=outcome,
                passed_point_of_no_return=has_passed_point_of_no_return(steps_before=plan.steps[:position]),
                prepared_steps=prepared_steps,
            )
        return SagaStatus.SUCCEEDED

    def _run_step(
        self, *, step: PreparableStep, step_results: StepResults, recorder: StepRecorder
    ) -> tuple[StepOutcome, PreparedStep | None]:
        prepared: PreparedStep | None = self._runner.start(
            step=step, step_results=step_results, recorder=recorder
        )
        if prepared is None:
            return StepOutcome.FAILED, None
        return self._runner.run_to_outcome(step=prepared, recorder=recorder), prepared

    def _status_after_stop(
        self,
        *,
        outcome: StepOutcome,
        passed_point_of_no_return: bool,
        prepared_steps: list[tuple[PreparedStep, StepRecorder]],
    ) -> SagaStatus:
        if not compensation_allowed(outcome=outcome, passed_point_of_no_return=passed_point_of_no_return):
            return SagaStatus.REQUIRES_MANUAL_INTERVENTION
        if self._compensator.compensate_in_reverse(prepared_steps=prepared_steps):
            return SagaStatus.ROLLED_BACK
        return SagaStatus.REQUIRES_MANUAL_INTERVENTION

    def _end(self, *, record: SagaRecord, plan: SagaPlan) -> None:
        logger.info(msg=f"saga {record.saga_id} ended {record.status.value}")
        self._record_writer.save_final(record=record)
        self._release_lock_if_cleanly_ended(record=record, plan=plan)

    def _release_lock_if_cleanly_ended(self, *, record: SagaRecord, plan: SagaPlan) -> None:
        if record.has_ended_cleanly():
            self._lock.release(lock_keys=plan.lock_keys, owner=record.saga_id)
            return
        logger.critical(msg=f"saga {record.saga_id} needs manual intervention, lock {plan.lock_keys} kept")
