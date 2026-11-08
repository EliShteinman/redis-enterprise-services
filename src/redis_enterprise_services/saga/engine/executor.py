import logging
from collections.abc import Callable

from redis_enterprise_services.saga.contract.kind import StepKind
from redis_enterprise_services.saga.contract.lock import DatabaseLock
from redis_enterprise_services.saga.contract.models import (
    SETTLED,
    SagaRecord,
    SagaStatus,
    StepRecord,
)
from redis_enterprise_services.saga.contract.state import SagaStateRepository
from redis_enterprise_services.saga.engine.compensator import Compensator
from redis_enterprise_services.saga.engine.recorder import StepRecorder
from redis_enterprise_services.saga.engine.step_runner import StepOutcome, StepRunner
from redis_enterprise_services.saga.plan.context import SagaContext
from redis_enterprise_services.saga.plan.runnable import PreparedStep, RunnableStep
from redis_enterprise_services.saga.plan.saga_plan import SagaPlan

logger: logging.Logger = logging.getLogger(name=__name__)


class SagaExecutor:
    def __init__(
        self,
        *,
        state: SagaStateRepository,
        lock: DatabaseLock,
        runner: StepRunner,
        compensator: Compensator,
    ) -> None:
        self._state: SagaStateRepository = state
        self._lock: DatabaseLock = lock
        self._runner: StepRunner = runner
        self._compensator: Compensator = compensator

    def run(
        self, *, saga_id: str, plan: SagaPlan, before_start: Callable[[], None] = lambda: None
    ) -> SagaRecord:
        self._lock.acquire(keys=plan.lock_keys, owner=saga_id)
        try:
            before_start()
            self._lock.confirm(keys=plan.lock_keys, owner=saga_id)
            record: SagaRecord = SagaRecord(
                saga_id=saga_id, steps=[StepRecord(key=step.key, kind=step.kind) for step in plan.steps]
            )
            self._state.save(record=record)
        except BaseException:
            logger.info(msg=f"saga {saga_id} did not start, {plan.lock_keys} released")
            self._lock.release(keys=plan.lock_keys, owner=saga_id)
            raise
        try:
            record.status = self._run_steps(plan=plan, record=record)
        finally:
            if record.status is SagaStatus.RUNNING:
                logger.error(msg=f"saga {saga_id} stopped on an unexpected error", exc_info=True)
                record.stop_running()
            self._finish(record=record, plan=plan)
        return record

    def _run_steps(self, *, plan: SagaPlan, record: SagaRecord) -> SagaStatus:
        context: SagaContext = SagaContext()
        started: list[tuple[PreparedStep, StepRecorder]] = []
        past_no_return: bool = False
        for step, step_record in zip(plan.steps, record.steps, strict=True):
            recorder: StepRecorder = StepRecorder(state=self._state, record=record, step=step_record)
            outcome, prepared = self._run_step(step=step, context=context, recorder=recorder)
            if prepared is not None:
                started.append((prepared, recorder))
            if outcome is StepOutcome.DONE:
                past_no_return = past_no_return or step.kind is not StepKind.COMPENSATABLE
                continue
            record.stopped_at = step.key
            return self._stopped(outcome=outcome, past_no_return=past_no_return, started=started)
        return SagaStatus.SUCCEEDED

    def _run_step(
        self, *, step: RunnableStep, context: SagaContext, recorder: StepRecorder
    ) -> tuple[StepOutcome, PreparedStep | None]:
        prepared: PreparedStep | None = self._runner.prepare(step=step, context=context, recorder=recorder)
        if prepared is None:
            return StepOutcome.FAILED, None
        return self._runner.run(step=prepared, recorder=recorder), prepared

    def _stopped(
        self, *, outcome: StepOutcome, past_no_return: bool, started: list[tuple[PreparedStep, StepRecorder]]
    ) -> SagaStatus:
        if outcome is StepOutcome.MANUAL or past_no_return:
            return SagaStatus.REQUIRES_MANUAL_INTERVENTION
        if self._compensator.compensate(steps=started):
            return SagaStatus.ROLLED_BACK
        return SagaStatus.REQUIRES_MANUAL_INTERVENTION

    def _finish(self, *, record: SagaRecord, plan: SagaPlan) -> None:
        logger.info(msg=f"saga {record.saga_id} ended {record.status.value}")
        if record.status in SETTLED:
            self._lock.release(keys=plan.lock_keys, owner=record.saga_id)
        else:
            logger.critical(
                msg=f"saga {record.saga_id} needs manual intervention, lock {plan.lock_keys} kept"
            )
        self._state.finish(record=record)
