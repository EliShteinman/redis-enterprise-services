import logging
from enum import StrEnum

from pydantic import ValidationError

from redis_enterprise_services.config.saga_settings import SagaSettings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.saga.contract.failure import Failure, FailureClassifier
from redis_enterprise_services.saga.contract.kind import StepKind
from redis_enterprise_services.saga.contract.models import StepError
from redis_enterprise_services.saga.engine.recorder import StepRecorder
from redis_enterprise_services.saga.engine.retry import pause
from redis_enterprise_services.saga.plan.context import SagaContext
from redis_enterprise_services.saga.plan.runnable import PreparedStep, RunnableStep
from redis_enterprise_services.timing.sleeper import Sleeper

logger: logging.Logger = logging.getLogger(name=__name__)


class StepOutcome(StrEnum):
    DONE = "done"
    FAILED = "failed"
    MANUAL = "manual"


class Check(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    FAILED = "failed"
    MANUAL = "manual"


class StepRunner:
    def __init__(self, *, settings: SagaSettings, classifier: FailureClassifier, sleeper: Sleeper) -> None:
        self._settings: SagaSettings = settings
        self._classifier: FailureClassifier = classifier
        self._sleeper: Sleeper = sleeper

    def prepare(
        self, *, step: RunnableStep, context: SagaContext, recorder: StepRecorder
    ) -> PreparedStep | None:
        logger.info(msg=f"step {step.key} started")
        try:
            prepared: PreparedStep = step.prepare(context=context)
        except RedisEnterpriseServicesError as error:
            return input_failed(step=step, recorder=recorder, error=StepError.of(error=error))
        except ValidationError as error:
            return input_failed(
                step=step,
                recorder=recorder,
                error=StepError(
                    code=RedisEnterpriseServicesError.code, message=f"cannot build the input: {error}"
                ),
            )
        recorder.started(step_input=prepared.step_input)
        return prepared

    def run(self, *, step: PreparedStep, recorder: StepRecorder) -> StepOutcome:
        outcome: StepOutcome = manual_if_cannot_undo(
            step=step, outcome=self._attempts(step=step, recorder=recorder)
        )
        if outcome is StepOutcome.DONE:
            recorder.done()
        elif outcome is StepOutcome.MANUAL:
            recorder.unresolved()
        else:
            recorder.failed()
        logger.info(msg=f"step {step.key} ended {outcome.value}")
        return outcome

    def _attempts(self, *, step: PreparedStep, recorder: StepRecorder) -> StepOutcome:
        attempts: int = self._settings.step_retry.attempts
        after_unknown: bool = False
        for attempt in range(1, attempts + 1):
            forget_unfound_result(step=step, recorder=recorder)
            failure: Failure | None = self._attempt(step=step, recorder=recorder)
            if failure is None:
                return StepOutcome.DONE
            outcome: StepOutcome | None = self._final_outcome(
                step=step, recorder=recorder, failure=failure, after_unknown=after_unknown
            )
            if outcome is not None:
                return outcome
            after_unknown = after_unknown or failure is Failure.UNKNOWN
            if attempt < attempts:
                pause(retry=self._settings.step_retry, attempt=attempt, sleeper=self._sleeper)
        return StepOutcome.MANUAL if after_unknown else StepOutcome.FAILED

    def _final_outcome(
        self, *, step: PreparedStep, recorder: StepRecorder, failure: Failure, after_unknown: bool
    ) -> StepOutcome | None:
        if failure is Failure.MANUAL or after_unknown:
            return StepOutcome.MANUAL
        if failure is not Failure.UNKNOWN and not step.has_result:
            return StepOutcome.FAILED if failure is Failure.FAILED else None
        match self._check(step=step, recorder=recorder):
            case Check.FOUND:
                return StepOutcome.DONE
            case Check.FAILED:
                return StepOutcome.FAILED
            case Check.MANUAL:
                return StepOutcome.MANUAL
            case Check.NOT_FOUND:
                return not_found_outcome(step=step, failure=failure)

    def _attempt(self, *, step: PreparedStep, recorder: StepRecorder) -> Failure | None:
        try:
            step.execute(on_kept=recorder.kept)
        except RedisEnterpriseServicesError as error:
            logger.warning(msg=f"step {step.key} failed: {error.coded_message()}")
            recorder.failed_attempt(error=StepError.of(error=error))
            return self._classifier.classify(error=error)
        return None

    def _check(self, *, step: PreparedStep, recorder: StepRecorder) -> Check:
        try:
            return Check.FOUND if step.resolve(on_kept=recorder.kept) else Check.NOT_FOUND
        except RedisEnterpriseServicesError as error:
            logger.error(msg=f"checking step {step.key} failed, its own error stays: {error.coded_message()}")
            if self._classifier.classify_lookup(error=error) is Failure.FAILED:
                return Check.FAILED
            return Check.MANUAL


def input_failed(*, step: RunnableStep, recorder: StepRecorder, error: StepError) -> None:
    logger.error(msg=f"cannot build the input of step {step.key}: {error.message}")
    recorder.failed_attempt(error=error)
    recorder.failed()


def forget_unfound_result(*, step: PreparedStep, recorder: StepRecorder) -> None:
    if step.has_result:
        logger.warning(msg=f"step {step.key} kept a result that was not found, it runs again without it")
        step.forget_result()
        recorder.result_forgotten()


def not_found_outcome(*, step: PreparedStep, failure: Failure) -> StepOutcome | None:
    if not step.has_result:
        return None
    if failure is Failure.TRANSIENT:
        return None if step.kind is StepKind.COMPENSATABLE else StepOutcome.MANUAL
    if failure is Failure.UNKNOWN:
        logger.error(msg=f"step {step.key} kept a result, and its unknown outcome was not found")
        return StepOutcome.MANUAL
    return StepOutcome.FAILED


def manual_if_cannot_undo(*, step: PreparedStep, outcome: StepOutcome) -> StepOutcome:
    if outcome is StepOutcome.FAILED and step.has_result and step.kind is not StepKind.COMPENSATABLE:
        logger.error(msg=f"step {step.key} kept a result that cannot be compensated")
        return StepOutcome.MANUAL
    return outcome
