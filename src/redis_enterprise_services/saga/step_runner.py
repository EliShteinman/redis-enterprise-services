import logging
from enum import StrEnum

from redis_enterprise_services.config.saga_settings import SagaSettings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.saga.context import SagaContext
from redis_enterprise_services.saga.failure import Failure, classify, classify_lookup
from redis_enterprise_services.saga.recorder import StepRecorder
from redis_enterprise_services.saga.retry import pause
from redis_enterprise_services.saga.runnable import RunnableStep

logger: logging.Logger = logging.getLogger(name=__name__)


class StepOutcome(StrEnum):
    DONE = "done"
    FAILED = "failed"
    MANUAL = "manual"
    NOT_FOUND = "not_found"


class StepRunner:
    def __init__(self, *, settings: SagaSettings) -> None:
        self._settings: SagaSettings = settings

    def run(self, *, step: RunnableStep, context: SagaContext, recorder: StepRecorder) -> StepOutcome:
        logger.info(msg=f"step {step.key} started")
        recorder.started(step_input=step.prepare(context=context))
        outcome: StepOutcome = self._attempts(step=step, recorder=recorder)
        if outcome is StepOutcome.DONE:
            recorder.done()
        else:
            recorder.failed()
        logger.info(msg=f"step {step.key} ended {outcome.value}")
        return outcome

    def _attempts(self, *, step: RunnableStep, recorder: StepRecorder) -> StepOutcome:
        attempts: int = self._settings.step_retry.attempts
        for attempt in range(1, attempts + 1):
            outcome: StepOutcome = self._attempt(step=step, recorder=recorder)
            if outcome is not StepOutcome.NOT_FOUND:
                return outcome
            if attempt < attempts:
                pause(retry=self._settings.step_retry, attempt=attempt)
        return StepOutcome.FAILED

    def _attempt(self, *, step: RunnableStep, recorder: StepRecorder) -> StepOutcome:
        try:
            step.execute(on_kept=recorder.kept)
        except RedisEnterpriseServicesError as error:
            logger.warning(msg=f"step {step.key} failed: {error.code}: {error.message}")
            recorder.failed_attempt(error=error.message)
            return self._after_failure(
                step=step,
                recorder=recorder,
                failure=classify(error=error, transient_codes=self._settings.transient_error_codes),
            )
        return StepOutcome.DONE

    def _after_failure(self, *, step: RunnableStep, recorder: StepRecorder, failure: Failure) -> StepOutcome:
        if failure is Failure.MANUAL:
            return StepOutcome.MANUAL
        if failure is Failure.FAILED:
            return StepOutcome.FAILED
        if failure is Failure.TRANSIENT and not step.has_result:
            return StepOutcome.NOT_FOUND
        return self._resolve(step=step, recorder=recorder)

    def _resolve(self, *, step: RunnableStep, recorder: StepRecorder) -> StepOutcome:
        attempts: int = self._settings.step_retry.attempts
        for attempt in range(1, attempts + 1):
            try:
                return StepOutcome.DONE if step.resolve(on_kept=recorder.kept) else StepOutcome.NOT_FOUND
            except RedisEnterpriseServicesError as error:
                logger.warning(msg=f"checking step {step.key} failed: {error.code}: {error.message}")
                recorder.failed_attempt(error=error.message)
                failure: Failure = classify_lookup(error=error)
                if failure is Failure.MANUAL:
                    return StepOutcome.MANUAL
                if failure is Failure.FAILED:
                    return StepOutcome.FAILED
            if attempt < attempts:
                pause(retry=self._settings.step_retry, attempt=attempt)
        logger.error(msg=f"the outcome of step {step.key} is still unknown")
        return StepOutcome.MANUAL
