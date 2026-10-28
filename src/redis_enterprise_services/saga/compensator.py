import logging

from redis_enterprise_services.config.saga_settings import SagaSettings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.saga.failure import describe
from redis_enterprise_services.saga.kind import StepKind
from redis_enterprise_services.saga.models import ObtainedBy
from redis_enterprise_services.saga.recorder import StepRecorder
from redis_enterprise_services.saga.retry import pause
from redis_enterprise_services.saga.runnable import RunnableStep

logger: logging.Logger = logging.getLogger(name=__name__)


class Compensator:
    def __init__(self, *, settings: SagaSettings) -> None:
        self._settings: SagaSettings = settings

    def compensate(self, *, steps: list[tuple[RunnableStep, StepRecorder]]) -> bool:
        all_undone: bool = True
        for step, recorder in reversed(steps):
            if step.kind is not StepKind.COMPENSATABLE or not step.has_result:
                continue
            all_undone = self._compensate(step=step, recorder=recorder) and all_undone
        return all_undone

    def _compensate(self, *, step: RunnableStep, recorder: StepRecorder) -> bool:
        if step.obtained_by is ObtainedBy.FOUND:
            logger.warning(msg=f"compensating {step.key}, which was found by name and may not be ours")
        recorder.compensating()
        error_message: str = ""
        attempts: int = self._settings.compensation_retry.attempts
        for attempt in range(1, attempts + 1):
            try:
                step.compensate()
            except RedisEnterpriseServicesError as error:
                logger.warning(msg=f"compensation of {step.key} failed: {error.code}: {error.message}")
                error_message = describe(error=error)
                if attempt < attempts:
                    pause(retry=self._settings.compensation_retry, attempt=attempt)
                continue
            logger.info(msg=f"step {step.key} compensated")
            recorder.compensated()
            return True
        logger.error(msg=f"compensation of {step.key} gave up: {error_message}")
        recorder.compensation_failed(error=error_message)
        return False
