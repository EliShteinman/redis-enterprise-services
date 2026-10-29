import logging

from redis_enterprise_services.saga.compensator import Compensator
from redis_enterprise_services.saga.context import SagaContext
from redis_enterprise_services.saga.kind import StepKind
from redis_enterprise_services.saga.lock import DatabaseLock
from redis_enterprise_services.saga.models import SETTLED, SagaRecord, SagaStatus, StepRecord, StepStatus
from redis_enterprise_services.saga.plan import SagaPlan
from redis_enterprise_services.saga.recorder import StepRecorder
from redis_enterprise_services.saga.runnable import RunnableStep
from redis_enterprise_services.saga.state import SagaStateRepository
from redis_enterprise_services.saga.step_runner import StepOutcome, StepRunner

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
        try:
            self._state.save(record=record)
        except Exception:
            self._lock.release(keys=plan.lock_keys, owner=saga_id)
            raise
        try:
            record.status = self._run_steps(plan=plan, record=record)
        except Exception:
            logger.exception(msg=f"saga {saga_id} stopped on an unexpected error")
            raise
        finally:
            if record.status is SagaStatus.RUNNING:
                stop_running(record=record)
            self._finish(record=record, plan=plan)
        return record

    def _run_steps(self, *, plan: SagaPlan, record: SagaRecord) -> SagaStatus:
        context: SagaContext = SagaContext()
        started: list[tuple[RunnableStep, StepRecorder]] = []
        past_no_return: bool = False
        for step, step_record in zip(plan.steps, record.steps, strict=True):
            recorder: StepRecorder = StepRecorder(state=self._state, record=record, step=step_record)
            started.append((step, recorder))
            outcome: StepOutcome = self._runner.run(step=step, context=context, recorder=recorder)
            if outcome is StepOutcome.DONE:
                past_no_return = past_no_return or step.kind is not StepKind.COMPENSATABLE
                continue
            if outcome is StepOutcome.MANUAL or past_no_return:
                return SagaStatus.REQUIRES_MANUAL_INTERVENTION
            if self._compensator.compensate(steps=started):
                return SagaStatus.ROLLED_BACK
            return SagaStatus.REQUIRES_MANUAL_INTERVENTION
        return SagaStatus.SUCCEEDED

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
