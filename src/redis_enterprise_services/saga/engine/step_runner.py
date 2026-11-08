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
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep, PreparedStep
from redis_enterprise_services.saga.plan.step_results import StepResults
from redis_enterprise_services.timing.sleeper import Sleeper

logger: logging.Logger = logging.getLogger(name=__name__)


class StepOutcome(StrEnum):
    DONE = "done"
    FAILED = "failed"
    REQUIRES_MANUAL_INTERVENTION = "requires_manual_intervention"


class FindOutcomeVerdict(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    FAILED = "failed"
    REQUIRES_MANUAL_INTERVENTION = "requires_manual_intervention"


class StepRunner:
    def __init__(self, *, settings: SagaSettings, classifier: FailureClassifier, sleeper: Sleeper) -> None:
        self._settings: SagaSettings = settings
        self._classifier: FailureClassifier = classifier
        self._sleeper: Sleeper = sleeper

    def prepare_and_mark_running(
        self, *, step: PreparableStep, step_results: StepResults, recorder: StepRecorder
    ) -> PreparedStep | None:
        logger.info(msg=f"step {step.key} started")
        try:
            prepared: PreparedStep = step.prepare(step_results=step_results)
        except RedisEnterpriseServicesError as error:
            return mark_input_build_failed(
                step=step, recorder=recorder, error=StepError.from_exception(error=error)
            )
        except ValidationError as error:
            return mark_input_build_failed(
                step=step,
                recorder=recorder,
                error=StepError(
                    code=RedisEnterpriseServicesError.code, message=f"cannot build the input: {error}"
                ),
            )
        recorder.mark_running(step_input=prepared.step_input)
        return prepared

    def run_and_mark_outcome(self, *, step: PreparedStep, recorder: StepRecorder) -> StepOutcome:
        outcome: StepOutcome = manual_if_failed_with_uncompensatable_result(
            step=step, outcome=self._run_with_retries(step=step, recorder=recorder)
        )
        if outcome is StepOutcome.DONE:
            recorder.mark_done()
        elif outcome is StepOutcome.REQUIRES_MANUAL_INTERVENTION:
            recorder.mark_unresolved()
        else:
            recorder.mark_failed()
        logger.info(msg=f"step {step.key} ended {outcome.value}")
        return outcome

    def _run_with_retries(self, *, step: PreparedStep, recorder: StepRecorder) -> StepOutcome:
        attempts: int = self._settings.step_retry.attempts
        had_unknown_outcome: bool = False
        for attempt in range(1, attempts + 1):
            forget_kept_result(step=step, recorder=recorder)
            failure: FailureCategory | None = self._execute_once(step=step, recorder=recorder)
            if failure is None:
                return StepOutcome.DONE
            outcome: StepOutcome | None = self._decide_or_find_outcome(
                step=step, recorder=recorder, failure=failure, had_unknown_outcome=had_unknown_outcome
            )
            if outcome is not None:
                return outcome
            had_unknown_outcome = had_unknown_outcome or failure is FailureCategory.OUTCOME_UNKNOWN
            if attempt < attempts:
                wait_before_retry(
                    retry_settings=self._settings.step_retry, attempt=attempt, sleeper=self._sleeper
                )
        return StepOutcome.REQUIRES_MANUAL_INTERVENTION if had_unknown_outcome else StepOutcome.FAILED

    def _decide_or_find_outcome(
        self,
        *,
        step: PreparedStep,
        recorder: StepRecorder,
        failure: FailureCategory,
        had_unknown_outcome: bool,
    ) -> StepOutcome | None:
        if failure is FailureCategory.REQUIRES_MANUAL_INTERVENTION or had_unknown_outcome:
            return StepOutcome.REQUIRES_MANUAL_INTERVENTION
        if failure is not FailureCategory.OUTCOME_UNKNOWN and not step.has_result:
            return StepOutcome.FAILED if failure is FailureCategory.FAILED else None
        match self._find_outcome(step=step, recorder=recorder):
            case FindOutcomeVerdict.FOUND:
                return StepOutcome.DONE
            case FindOutcomeVerdict.FAILED:
                return StepOutcome.FAILED
            case FindOutcomeVerdict.REQUIRES_MANUAL_INTERVENTION:
                return StepOutcome.REQUIRES_MANUAL_INTERVENTION
            case FindOutcomeVerdict.NOT_FOUND:
                return outcome_when_not_found(step=step, failure=failure)

    def _execute_once(self, *, step: PreparedStep, recorder: StepRecorder) -> FailureCategory | None:
        try:
            step.execute(on_result_kept=recorder.save_result)
        except RedisEnterpriseServicesError as error:
            logger.warning(msg=f"an attempt of step {step.key} failed: {error.coded_message()}")
            recorder.save_error(error=StepError.from_exception(error=error))
            return self._classifier.classify_step_error(error=error)
        return None

    def _find_outcome(self, *, step: PreparedStep, recorder: StepRecorder) -> FindOutcomeVerdict:
        try:
            return (
                FindOutcomeVerdict.FOUND
                if step.find_outcome(on_result_kept=recorder.save_result)
                else FindOutcomeVerdict.NOT_FOUND
            )
        except RedisEnterpriseServicesError as error:
            logger.error(
                msg=f"finding the outcome of step {step.key} failed, the step's own error stays: "
                f"{error.coded_message()}"
            )
            if self._classifier.classify_find_outcome_error(error=error) is FailureCategory.FAILED:
                return FindOutcomeVerdict.FAILED
            return FindOutcomeVerdict.REQUIRES_MANUAL_INTERVENTION


def mark_input_build_failed(*, step: PreparableStep, recorder: StepRecorder, error: StepError) -> None:
    logger.error(msg=f"cannot build the input of step {step.key}: {error.message}")
    recorder.save_error(error=error)
    recorder.mark_failed()


def forget_kept_result(*, step: PreparedStep, recorder: StepRecorder) -> None:
    if step.has_result:
        logger.warning(msg=f"step {step.key} kept a result that was not found, it runs again without it")
        step.forget_result()
        recorder.clear_saved_result()


def outcome_when_not_found(*, step: PreparedStep, failure: FailureCategory) -> StepOutcome | None:
    if not step.has_result:
        return None
    if failure is FailureCategory.TRANSIENT:
        return None if step.kind is StepKind.COMPENSATABLE else StepOutcome.REQUIRES_MANUAL_INTERVENTION
    if failure is FailureCategory.OUTCOME_UNKNOWN:
        logger.error(msg=f"step {step.key} kept a result, and its unknown outcome was not found")
        return StepOutcome.REQUIRES_MANUAL_INTERVENTION
    return StepOutcome.FAILED


def manual_if_failed_with_uncompensatable_result(*, step: PreparedStep, outcome: StepOutcome) -> StepOutcome:
    if outcome is StepOutcome.FAILED and step.has_result and step.kind is not StepKind.COMPENSATABLE:
        logger.error(msg=f"step {step.key} kept a result that cannot be compensated")
        return StepOutcome.REQUIRES_MANUAL_INTERVENTION
    return outcome
