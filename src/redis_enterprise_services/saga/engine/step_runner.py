import logging
from enum import StrEnum

from pydantic import ValidationError

from redis_enterprise_services.config.saga_settings import SagaSettings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.saga.contract.failure import FailureCategory, FailureClassifier
from redis_enterprise_services.saga.contract.saga_record import StepError
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.saga.engine.backoff import wait_before_retry
from redis_enterprise_services.saga.engine.step_recorder import StepRecorder
from redis_enterprise_services.saga.plan.saga_context import SagaContext
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep, PreparedStep
from redis_enterprise_services.timing.sleeper import Sleeper

logger: logging.Logger = logging.getLogger(name=__name__)


class StepOutcome(StrEnum):
    DONE = "done"
    FAILED = "failed"
    REQUIRES_MANUAL_INTERVENTION = "requires_manual_intervention"


class FindOutcomeResult(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    REJECTED = "rejected"
    REQUIRES_MANUAL_INTERVENTION = "requires_manual_intervention"


class StepRunner:
    def __init__(self, *, settings: SagaSettings, classifier: FailureClassifier, sleeper: Sleeper) -> None:
        self._settings: SagaSettings = settings
        self._classifier: FailureClassifier = classifier
        self._sleeper: Sleeper = sleeper

    def prepare(
        self, *, step: PreparableStep, context: SagaContext, recorder: StepRecorder
    ) -> PreparedStep | None:
        logger.info(msg=f"step {step.key} started")
        try:
            prepared: PreparedStep = step.prepare(context=context)
        except RedisEnterpriseServicesError as error:
            return record_input_failure(
                step=step, recorder=recorder, error=StepError.from_exception(error=error)
            )
        except ValidationError as error:
            return record_input_failure(
                step=step,
                recorder=recorder,
                error=StepError(
                    code=RedisEnterpriseServicesError.code, message=f"cannot build the input: {error}"
                ),
            )
        recorder.started(step_input=prepared.step_input)
        return prepared

    def run(self, *, step: PreparedStep, recorder: StepRecorder) -> StepOutcome:
        outcome: StepOutcome = manual_if_not_compensatable(
            step=step, outcome=self._outcome_after_retries(step=step, recorder=recorder)
        )
        if outcome is StepOutcome.DONE:
            recorder.done()
        elif outcome is StepOutcome.REQUIRES_MANUAL_INTERVENTION:
            recorder.unresolved()
        else:
            recorder.failed()
        logger.info(msg=f"step {step.key} ended {outcome.value}")
        return outcome

    def _outcome_after_retries(self, *, step: PreparedStep, recorder: StepRecorder) -> StepOutcome:
        attempts: int = self._settings.step_retry.attempts
        had_unknown_outcome: bool = False
        for attempt in range(1, attempts + 1):
            forget_kept_result(step=step, recorder=recorder)
            failure: FailureCategory | None = self._try_once(step=step, recorder=recorder)
            if failure is None:
                return StepOutcome.DONE
            outcome: StepOutcome | None = self._decide_after_failure(
                step=step, recorder=recorder, failure=failure, had_unknown_outcome=had_unknown_outcome
            )
            if outcome is not None:
                return outcome
            had_unknown_outcome = had_unknown_outcome or failure is FailureCategory.UNKNOWN
            if attempt < attempts:
                wait_before_retry(
                    retry_settings=self._settings.step_retry, attempt=attempt, sleeper=self._sleeper
                )
        return StepOutcome.REQUIRES_MANUAL_INTERVENTION if had_unknown_outcome else StepOutcome.FAILED

    def _decide_after_failure(
        self,
        *,
        step: PreparedStep,
        recorder: StepRecorder,
        failure: FailureCategory,
        had_unknown_outcome: bool,
    ) -> StepOutcome | None:
        if failure is FailureCategory.REQUIRES_MANUAL_INTERVENTION or had_unknown_outcome:
            return StepOutcome.REQUIRES_MANUAL_INTERVENTION
        if failure is not FailureCategory.UNKNOWN and not step.has_result:
            return StepOutcome.FAILED if failure is FailureCategory.REJECTED else None
        match self._find_outcome(step=step, recorder=recorder):
            case FindOutcomeResult.FOUND:
                return StepOutcome.DONE
            case FindOutcomeResult.REJECTED:
                return StepOutcome.FAILED
            case FindOutcomeResult.REQUIRES_MANUAL_INTERVENTION:
                return StepOutcome.REQUIRES_MANUAL_INTERVENTION
            case FindOutcomeResult.NOT_FOUND:
                return outcome_when_not_found(step=step, failure=failure)

    def _try_once(self, *, step: PreparedStep, recorder: StepRecorder) -> FailureCategory | None:
        try:
            step.execute(on_result_kept=recorder.result_kept)
        except RedisEnterpriseServicesError as error:
            logger.warning(msg=f"step {step.key} failed: {error.coded_message()}")
            recorder.attempt_failed(error=StepError.from_exception(error=error))
            return self._classifier.classify_step_error(error=error)
        return None

    def _find_outcome(self, *, step: PreparedStep, recorder: StepRecorder) -> FindOutcomeResult:
        try:
            return (
                FindOutcomeResult.FOUND
                if step.find_outcome(on_result_kept=recorder.result_kept)
                else FindOutcomeResult.NOT_FOUND
            )
        except RedisEnterpriseServicesError as error:
            logger.error(msg=f"checking step {step.key} failed, its own error stays: {error.coded_message()}")
            if self._classifier.classify_find_outcome_error(error=error) is FailureCategory.REJECTED:
                return FindOutcomeResult.REJECTED
            return FindOutcomeResult.REQUIRES_MANUAL_INTERVENTION


def record_input_failure(*, step: PreparableStep, recorder: StepRecorder, error: StepError) -> None:
    logger.error(msg=f"cannot build the input of step {step.key}: {error.message}")
    recorder.attempt_failed(error=error)
    recorder.failed()


def forget_kept_result(*, step: PreparedStep, recorder: StepRecorder) -> None:
    if step.has_result:
        logger.warning(msg=f"step {step.key} kept a result that was not found, it runs again without it")
        step.forget_result()
        recorder.result_forgotten()


def outcome_when_not_found(*, step: PreparedStep, failure: FailureCategory) -> StepOutcome | None:
    if not step.has_result:
        return None
    if failure is FailureCategory.TRANSIENT:
        return None if step.kind is StepKind.COMPENSATABLE else StepOutcome.REQUIRES_MANUAL_INTERVENTION
    if failure is FailureCategory.UNKNOWN:
        logger.error(msg=f"step {step.key} kept a result, and its unknown outcome was not found")
        return StepOutcome.REQUIRES_MANUAL_INTERVENTION
    return StepOutcome.FAILED


def manual_if_not_compensatable(*, step: PreparedStep, outcome: StepOutcome) -> StepOutcome:
    if outcome is StepOutcome.FAILED and step.has_result and step.kind is not StepKind.COMPENSATABLE:
        logger.error(msg=f"step {step.key} kept a result that cannot be compensated")
        return StepOutcome.REQUIRES_MANUAL_INTERVENTION
    return outcome
