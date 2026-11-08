import logging
from collections.abc import Callable

from redis_enterprise_services.saga.contract.saga_lock import SagaLock
from redis_enterprise_services.saga.contract.saga_record import (
    SETTLED_STATUSES,
    SagaRecord,
    SagaStatus,
    StepRecord,
)
from redis_enterprise_services.saga.contract.saga_record_store import SagaRecordWriter
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.saga.engine.compensator import Compensator
from redis_enterprise_services.saga.engine.step_recorder import StepRecorder
from redis_enterprise_services.saga.engine.step_runner import StepOutcome, StepRunner
from redis_enterprise_services.saga.plan.saga_context import SagaContext
from redis_enterprise_services.saga.plan.saga_plan import SagaPlan
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep, PreparedStep

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
        self._lock.acquire(keys=plan.lock_keys, owner=saga_id)
        try:
            check_before_start()
            self._lock.ensure_held(keys=plan.lock_keys, owner=saga_id)
            record: SagaRecord = SagaRecord(
                saga_id=saga_id, steps=[StepRecord(key=step.key, kind=step.kind) for step in plan.steps]
            )
            self._record_writer.save(record=record)
        except BaseException:
            logger.info(msg=f"saga {saga_id} did not start, {plan.lock_keys} released")
            self._lock.release(keys=plan.lock_keys, owner=saga_id)
            raise
        try:
            record.status = self._run_steps(plan=plan, record=record)
        finally:
            if record.status is SagaStatus.RUNNING:
                logger.error(msg=f"saga {saga_id} stopped on an unexpected error", exc_info=True)
                record.mark_interrupted()
            self._finish(record=record, plan=plan)
        return record

    def _run_steps(self, *, plan: SagaPlan, record: SagaRecord) -> SagaStatus:
        context: SagaContext = SagaContext()
        prepared_steps: list[tuple[PreparedStep, StepRecorder]] = []
        passed_point_of_no_return: bool = False
        for step, step_record in zip(plan.steps, record.steps, strict=True):
            recorder: StepRecorder = StepRecorder(
                record_writer=self._record_writer, record=record, step_record=step_record
            )
            outcome, prepared = self._run_step(step=step, context=context, recorder=recorder)
            if prepared is not None:
                prepared_steps.append((prepared, recorder))
            if outcome is StepOutcome.DONE:
                passed_point_of_no_return = (
                    passed_point_of_no_return or step.kind is not StepKind.COMPENSATABLE
                )
                continue
            record.stopped_at = step.key
            return self._status_after_stop(
                outcome=outcome,
                passed_point_of_no_return=passed_point_of_no_return,
                prepared_steps=prepared_steps,
            )
        return SagaStatus.SUCCEEDED

    def _run_step(
        self, *, step: PreparableStep, context: SagaContext, recorder: StepRecorder
    ) -> tuple[StepOutcome, PreparedStep | None]:
        prepared: PreparedStep | None = self._runner.prepare(step=step, context=context, recorder=recorder)
        if prepared is None:
            return StepOutcome.FAILED, None
        return self._runner.run(step=prepared, recorder=recorder), prepared

    def _status_after_stop(
        self,
        *,
        outcome: StepOutcome,
        passed_point_of_no_return: bool,
        prepared_steps: list[tuple[PreparedStep, StepRecorder]],
    ) -> SagaStatus:
        if outcome is StepOutcome.REQUIRES_MANUAL_INTERVENTION or passed_point_of_no_return:
            return SagaStatus.REQUIRES_MANUAL_INTERVENTION
        if self._compensator.compensate_all(steps=prepared_steps):
            return SagaStatus.ROLLED_BACK
        return SagaStatus.REQUIRES_MANUAL_INTERVENTION

    def _finish(self, *, record: SagaRecord, plan: SagaPlan) -> None:
        logger.info(msg=f"saga {record.saga_id} ended {record.status.value}")
        if record.status in SETTLED_STATUSES:
            self._lock.release(keys=plan.lock_keys, owner=record.saga_id)
        else:
            logger.critical(
                msg=f"saga {record.saga_id} needs manual intervention, lock {plan.lock_keys} kept"
            )
        self._record_writer.save_final(record=record)
