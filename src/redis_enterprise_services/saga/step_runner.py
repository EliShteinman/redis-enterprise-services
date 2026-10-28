import logging
from enum import StrEnum

from pydantic import JsonValue, ValidationError

from redis_enterprise_services.config.saga_settings import SagaSettings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.saga.context import SagaContext
from redis_enterprise_services.saga.failure import Failure, FailureClassifier, describe
from redis_enterprise_services.saga.recorder import StepRecorder
from redis_enterprise_services.saga.retry import pause
from redis_enterprise_services.saga.runnable import RunnableStep
from redis_enterprise_services.steps.kind import StepKind

logger: logging.Logger = logging.getLogger(name=__name__)


class StepOutcome(StrEnum):
    DONE = "done"
    FAILED = "failed"
    MANUAL = "manual"
    NOT_FOUND = "not_found"


class StepRunner:
    def __init__(self, *, settings: SagaSettings, classifier: FailureClassifier) -> None:
        self._settings: SagaSettings = settings
        self._classifier: FailureClassifier = classifier

    def run(self, *, step: RunnableStep, context: SagaContext, recorder: StepRecorder) -> StepOutcome:
        logger.info(msg=f"step {step.key} started")
        try:
            step_input: JsonValue = step.prepare(context=context)
        except (RedisEnterpriseServicesError, ValidationError) as error:
            logger.error(msg=f"cannot build the input of step {step.key}: {error}")
            recorder.failed_attempt(error=f"cannot build the input: {error}")
            recorder.failed()
            return StepOutcome.FAILED
        recorder.started(step_input=step_input)
        outcome: StepOutcome = self._settled(step=step, outcome=self._attempts(step=step, recorder=recorder))
        if outcome is StepOutcome.DONE:
            recorder.done()
        elif outcome is StepOutcome.MANUAL:
            recorder.unresolved()
        else:
            recorder.failed()
        logger.info(msg=f"step {step.key} ended {outcome.value}")
        return outcome

    @staticmethod
    def _settled(*, step: RunnableStep, outcome: StepOutcome) -> StepOutcome:
        if outcome is StepOutcome.FAILED and step.has_result and step.kind is not StepKind.COMPENSATABLE:
            logger.error(msg=f"step {step.key} kept a result that cannot be compensated")
            return StepOutcome.MANUAL
        return outcome

    def _attempts(self, *, step: RunnableStep, recorder: StepRecorder) -> StepOutcome:
        attempts: int = self._settings.step_retry.attempts
        uncertain: bool = False
        for attempt in range(1, attempts + 1):
            failure: Failure | None = self._attempt(step=step, recorder=recorder)
            if failure is None:
                return StepOutcome.DONE
            if failure is Failure.MANUAL:
                return StepOutcome.MANUAL
            if failure is Failure.UNKNOWN or uncertain or step.has_result:
                uncertain = True
                outcome: StepOutcome = self._resolve(step=step, recorder=recorder)
                if outcome is not StepOutcome.NOT_FOUND:
                    return outcome
                if failure is Failure.FAILED or step.has_result:
                    return self._not_found(step=step)
            elif failure is Failure.FAILED:
                return StepOutcome.FAILED
            if attempt < attempts:
                pause(retry=self._settings.step_retry, attempt=attempt)
        return self._not_found(step=step) if uncertain else StepOutcome.FAILED

    @staticmethod
    def _not_found(*, step: RunnableStep) -> StepOutcome:
        if step.has_result:
            return StepOutcome.FAILED
        logger.error(msg=f"step {step.key} may have run, but it is not found")
        return StepOutcome.MANUAL

    def _attempt(self, *, step: RunnableStep, recorder: StepRecorder) -> Failure | None:
        try:
            step.execute(on_kept=recorder.kept)
        except RedisEnterpriseServicesError as error:
            logger.warning(msg=f"step {step.key} failed: {error.code}: {error.message}")
            recorder.failed_attempt(error=describe(error=error))
            return self._classifier.classify(error=error)
        return None

    def _resolve(self, *, step: RunnableStep, recorder: StepRecorder) -> StepOutcome:
        attempts: int = self._settings.step_retry.attempts
        for attempt in range(1, attempts + 1):
            try:
                return StepOutcome.DONE if step.resolve(on_kept=recorder.kept) else StepOutcome.NOT_FOUND
            except RedisEnterpriseServicesError as error:
                logger.warning(msg=f"checking step {step.key} failed: {error.code}: {error.message}")
                recorder.failed_attempt(error=describe(error=error))
                failure: Failure = self._classifier.classify_lookup(error=error)
                if failure is Failure.MANUAL:
                    return StepOutcome.MANUAL
                if failure is Failure.FAILED:
                    return StepOutcome.FAILED
            if attempt < attempts:
                pause(retry=self._settings.step_retry, attempt=attempt)
        logger.error(msg=f"the outcome of step {step.key} is still unknown")
        return StepOutcome.MANUAL
