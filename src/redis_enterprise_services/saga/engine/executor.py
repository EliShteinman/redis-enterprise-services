import logging

from redis_enterprise_services.saga.contract.kind import StepKind
from redis_enterprise_services.saga.contract.lock import DatabaseLock
from redis_enterprise_services.saga.contract.models import (
    SETTLED,
    SagaRecord,
    SagaStatus,
    StepRecord,
    StepStatus,
)
from redis_enterprise_services.saga.contract.state import SagaStateRepository
from redis_enterprise_services.saga.engine.compensator import Compensator
from redis_enterprise_services.saga.engine.recorder import StepRecorder
from redis_enterprise_services.saga.engine.step_runner import StepOutcome, StepRunner
from redis_enterprise_services.saga.plan.context import SagaContext
from redis_enterprise_services.saga.plan.plan import SagaPlan
from redis_enterprise_services.saga.plan.runnable import PreparedStep, RunnableStep

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

    def run(self, *, saga_id: str, plan: SagaPlan) -> SagaRecord:
        self._lock.acquire(keys=plan.lock_keys, owner=saga_id)
        record: SagaRecord = SagaRecord(
            saga_id=saga_id, steps=[StepRecord(key=step.key, kind=step.kind) for step in plan.steps]
        )
        self._state.save(record=record)
        try:
            record.status = self._run_steps(plan=plan, record=record)
        finally:
            if record.status is SagaStatus.RUNNING:
                logger.error(msg=f"saga {saga_id} stopped on an unexpected error", exc_info=True)
                stop_running(record=record)
            self._finish(record=record, plan=plan)
        return record

    def _run_steps(self, *, plan: SagaPlan, record: SagaRecord) -> SagaStatus:
        context: SagaContext = SagaContext()
        started: list[tuple[PreparedStep, StepRecorder]] = []
        past_no_return: bool = False
        for step, step_record in zip(plan.steps, record.steps, strict=True):
            recorder: StepRecorder = StepRecorder(state=self._state, record=record, step=step_record)
            outcome: StepOutcome = self._run_step(
                step=step, context=context, recorder=recorder, started=started
            )
            if outcome is StepOutcome.DONE:
                past_no_return = past_no_return or step.kind is not StepKind.COMPENSATABLE
                continue
            return self._stopped(outcome=outcome, past_no_return=past_no_return, started=started)
        return SagaStatus.SUCCEEDED

    def _run_step(
        self,
        *,
        step: RunnableStep,
        context: SagaContext,
        recorder: StepRecorder,
        started: list[tuple[PreparedStep, StepRecorder]],
    ) -> StepOutcome:
        prepared: PreparedStep | None = self._runner.prepare(step=step, context=context, recorder=recorder)
        if prepared is None:
            return StepOutcome.FAILED
        started.append((prepared, recorder))
        return self._runner.run(step=prepared, recorder=recorder)

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


def stop_running(*, record: SagaRecord) -> None:
    record.status = SagaStatus.REQUIRES_MANUAL_INTERVENTION
    for step in record.steps:
        if step.status is StepStatus.RUNNING:
            step.status = StepStatus.UNRESOLVED
