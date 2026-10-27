import logging

from redis_enterprise_services.saga.compensator import Compensator
from redis_enterprise_services.saga.context import SagaContext
from redis_enterprise_services.saga.lock import DatabaseLock
from redis_enterprise_services.saga.models import SagaRecord, SagaStatus, StepRecord
from redis_enterprise_services.saga.plan import SagaPlan
from redis_enterprise_services.saga.recorder import StepRecorder
from redis_enterprise_services.saga.runnable import RunnableStep
from redis_enterprise_services.saga.state import SagaStateRepository
from redis_enterprise_services.saga.step_runner import StepOutcome, StepRunner
from redis_enterprise_services.steps.kind import StepKind

logger: logging.Logger = logging.getLogger(name=__name__)


RELEASED_ON: frozenset[SagaStatus] = frozenset({SagaStatus.SUCCEEDED, SagaStatus.ROLLED_BACK})


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
            record.status = self._run_steps(plan=plan, record=record)
        except Exception:
            logger.exception(msg=f"saga {saga_id} stopped on an unexpected error")
            raise
        finally:
            if record.status is SagaStatus.RUNNING:
                record.status = SagaStatus.REQUIRES_MANUAL_INTERVENTION
            self._finish(record=record, plan=plan)
        return record

    def _run_steps(self, *, plan: SagaPlan, record: SagaRecord) -> SagaStatus:
        context: SagaContext = SagaContext()
        started: list[tuple[RunnableStep, StepRecorder]] = []
        pivot_done: bool = False
        for step, step_record in zip(plan.steps, record.steps, strict=True):
            recorder: StepRecorder = StepRecorder(state=self._state, record=record, step=step_record)
            started.append((step, recorder))
            outcome: StepOutcome = self._runner.run(step=step, context=context, recorder=recorder)
            if outcome is StepOutcome.DONE:
                pivot_done = pivot_done or step.kind is StepKind.PIVOT
                continue
            if outcome is StepOutcome.MANUAL or pivot_done:
                return SagaStatus.REQUIRES_MANUAL_INTERVENTION
            if self._compensator.compensate(steps=started):
                return SagaStatus.ROLLED_BACK
            return SagaStatus.REQUIRES_MANUAL_INTERVENTION
        return SagaStatus.SUCCEEDED

    def _finish(self, *, record: SagaRecord, plan: SagaPlan) -> None:
        self._state.finish(record=record)
        logger.info(msg=f"saga {record.saga_id} ended {record.status.value}")
        if record.status not in RELEASED_ON:
            logger.critical(
                msg=f"saga {record.saga_id} needs manual intervention, lock {plan.lock_keys} kept"
            )
            return
        self._lock.release(keys=plan.lock_keys, owner=record.saga_id)
