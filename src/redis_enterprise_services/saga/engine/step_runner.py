import logging
from enum import StrEnum

from pydantic import ValidationError

from redis_enterprise_services.config.saga_settings import SagaSettings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.saga.contract.failure import FailureCategory, FailureClassifier
from redis_enterprise_services.saga.contract.saga_record import StepError
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.saga.engine.step_recorder import StepRecorder
from redis_enterprise_services.saga.plan.step_protocols import PreparableStep, PreparedStep
from redis_enterprise_services.saga.plan.step_results import StepResults
from redis_enterprise_services.timing.paced_attempts import paced_attempts
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


class NextAfterFailure(StrEnum):
    REQUIRES_MANUAL_INTERVENTION = "requires_manual_intervention"
    FAILED = "failed"
    RETRY = "retry"
    FIND_OUTCOME = "find_outcome"


class StepRunner:
    def __init__(self, *, settings: SagaSettings, classifier: FailureClassifier, sleeper: Sleeper) -> None:
        self._settings: SagaSettings = settings
        self._classifier: FailureClassifier = classifier
        self._sleeper: Sleeper = sleeper

    def start(
        self, *, step: PreparableStep, step_results: StepResults, recorder: StepRecorder
    ) -> PreparedStep | None:
        logger.info(msg=f"step {step.key} started")
        try:
            prepared: PreparedStep = step.prepare(step_results=step_results)
        except RedisEnterpriseServicesError as error:
            mark_input_build_failed(step=step, recorder=recorder, error=StepError.from_exception(error=error))
            return None
        except ValidationError as error:
            mark_input_build_failed(
                step=step, recorder=recorder, error=StepError.from_input_validation_error(error=error)
            )
            return None
        recorder.mark_running(step_input=prepared.step_input)
        return prepared

    def run_to_outcome(self, *, step: PreparedStep, recorder: StepRecorder) -> StepOutcome:
        attempts_outcome: StepOutcome = self._run_with_retries(step=step, recorder=recorder)
        outcome: StepOutcome = escalated_outcome(
            outcome=attempts_outcome, has_result=step.has_result, kind=step.kind
        )
        if outcome is not attempts_outcome:
            logger.error(
                msg=f"step {step.key} ended {attempts_outcome.value} in a way the saga cannot compensate, "
                f"it needs manual intervention"
            )
        mark_outcome(recorder=recorder, outcome=outcome)
        logger.info(msg=f"step {step.key} ended {outcome.value}")
        return outcome

    def _run_with_retries(self, *, step: PreparedStep, recorder: StepRecorder) -> StepOutcome:
        had_unknown_outcome: bool = False
        for _attempt in paced_attempts(
            attempts=self._settings.step_retry.attempts,
            backoff_step_seconds=self._settings.step_retry.backoff_step_seconds,
            sleeper=self._sleeper,
        ):
            forget_kept_result(step=step, recorder=recorder)
            failure: FailureCategory | None = self._execute_once(step=step, recorder=recorder)
            if failure is None:
                return StepOutcome.DONE
            outcome: StepOutcome | None = self._outcome_after_failure(
                step=step, recorder=recorder, failure=failure, had_unknown_outcome=had_unknown_outcome
            )
            if outcome is not None:
                return outcome
            had_unknown_outcome = had_unknown_outcome or failure is FailureCategory.OUTCOME_UNKNOWN
        return outcome_when_attempts_run_out(had_unknown_outcome=had_unknown_outcome)

    def _outcome_after_failure(
        self,
        *,
        step: PreparedStep,
        recorder: StepRecorder,
        failure: FailureCategory,
        had_unknown_outcome: bool,
    ) -> StepOutcome | None:
        match next_after_failure(
            failure=failure, had_unknown_outcome=had_unknown_outcome, has_result=step.has_result
        ):
            case NextAfterFailure.REQUIRES_MANUAL_INTERVENTION:
                return StepOutcome.REQUIRES_MANUAL_INTERVENTION
            case NextAfterFailure.FAILED:
                return StepOutcome.FAILED
            case NextAfterFailure.RETRY:
                return None
            case NextAfterFailure.FIND_OUTCOME:
                return self._outcome_from_finding(step=step, recorder=recorder, failure=failure)

    def _outcome_from_finding(
        self, *, step: PreparedStep, recorder: StepRecorder, failure: FailureCategory
    ) -> StepOutcome | None:
        verdict: FindOutcomeVerdict = self._find_outcome(step=step, recorder=recorder)
        outcome: StepOutcome | None = outcome_from_verdict(
            verdict=verdict, failure=failure, has_result=step.has_result, kind=step.kind
        )
        if verdict is FindOutcomeVerdict.NOT_FOUND and outcome is StepOutcome.REQUIRES_MANUAL_INTERVENTION:
            logger.error(msg=f"step {step.key} kept a result, and its {failure.value} outcome was not found")
        return outcome

    def _execute_once(self, *, step: PreparedStep, recorder: StepRecorder) -> FailureCategory | None:
        try:
            step.execute(on_result_kept=recorder.save_result)
        except RedisEnterpriseServicesError as error:
            logger.warning(msg=f"an attempt of step {step.key} failed: {error.coded_message()}")
            recorder.save_error(error=StepError.from_exception(error=error))
            return self._classifier.classify_step_error(error=error)
        return None

    def _find_outcome(self, *, step: PreparedStep, recorder: StepRecorder) -> FindOutcomeVerdict:
        for _attempt in paced_attempts(
            attempts=self._settings.step_retry.attempts,
            backoff_step_seconds=self._settings.step_retry.backoff_step_seconds,
            sleeper=self._sleeper,
        ):
            verdict: FindOutcomeVerdict | None = self._find_outcome_once(step=step, recorder=recorder)
            if verdict is not None:
                return verdict
        logger.error(msg=f"finding the outcome of step {step.key} kept failing on transient errors")
        return FindOutcomeVerdict.REQUIRES_MANUAL_INTERVENTION

    def _find_outcome_once(self, *, step: PreparedStep, recorder: StepRecorder) -> FindOutcomeVerdict | None:
        try:
            return (
                FindOutcomeVerdict.FOUND
                if step.find_outcome(on_result_kept=recorder.save_result)
                else FindOutcomeVerdict.NOT_FOUND
            )
        except RedisEnterpriseServicesError as error:
            category: FailureCategory = self._classifier.classify_find_outcome_error(error=error)
            logger.warning(
                msg=f"finding the outcome of step {step.key} failed ({category.value}), the step's own "
                f"error stays: {error.coded_message()}"
            )
            return verdict_after_find_outcome_error(category=category)


def verdict_after_find_outcome_error(*, category: FailureCategory) -> FindOutcomeVerdict | None:
    match category:
        case FailureCategory.TRANSIENT:
            return None
        case FailureCategory.FAILED:
            return FindOutcomeVerdict.FAILED
        case FailureCategory.OUTCOME_UNKNOWN | FailureCategory.REQUIRES_MANUAL_INTERVENTION:
            return FindOutcomeVerdict.REQUIRES_MANUAL_INTERVENTION


def mark_input_build_failed(*, step: PreparableStep, recorder: StepRecorder, error: StepError) -> None:
    logger.error(msg=f"cannot build the input of step {step.key}: {error.message}")
    recorder.mark_failed_with_error(error=error)


def forget_kept_result(*, step: PreparedStep, recorder: StepRecorder) -> None:
    if step.has_result:
        logger.warning(msg=f"step {step.key} kept a result that was not found, it runs again without it")
        step.forget_result()
        recorder.clear_saved_result()


def mark_outcome(*, recorder: StepRecorder, outcome: StepOutcome) -> None:
    match outcome:
        case StepOutcome.DONE:
            recorder.mark_done()
        case StepOutcome.REQUIRES_MANUAL_INTERVENTION:
            recorder.mark_unresolved()
        case StepOutcome.FAILED:
            recorder.mark_failed()


def next_after_failure(
    *, failure: FailureCategory, had_unknown_outcome: bool, has_result: bool
) -> NextAfterFailure:
    if failure is FailureCategory.REQUIRES_MANUAL_INTERVENTION or had_unknown_outcome:
        return NextAfterFailure.REQUIRES_MANUAL_INTERVENTION
    if failure is not FailureCategory.OUTCOME_UNKNOWN and not has_result:
        return NextAfterFailure.FAILED if failure is FailureCategory.FAILED else NextAfterFailure.RETRY
    return NextAfterFailure.FIND_OUTCOME


def outcome_from_verdict(
    *, verdict: FindOutcomeVerdict, failure: FailureCategory, has_result: bool, kind: StepKind
) -> StepOutcome | None:
    match verdict:
        case FindOutcomeVerdict.FOUND:
            return StepOutcome.DONE
        case FindOutcomeVerdict.FAILED:
            return StepOutcome.FAILED
        case FindOutcomeVerdict.REQUIRES_MANUAL_INTERVENTION:
            return StepOutcome.REQUIRES_MANUAL_INTERVENTION
        case FindOutcomeVerdict.NOT_FOUND:
            return outcome_when_not_found(failure=failure, has_result=has_result, kind=kind)


def outcome_when_not_found(
    *, failure: FailureCategory, has_result: bool, kind: StepKind
) -> StepOutcome | None:
    if not has_result:
        return None
    if failure is FailureCategory.TRANSIENT:
        return None if kind is StepKind.COMPENSATABLE else StepOutcome.REQUIRES_MANUAL_INTERVENTION
    if failure is FailureCategory.OUTCOME_UNKNOWN:
        return StepOutcome.REQUIRES_MANUAL_INTERVENTION
    return StepOutcome.FAILED


def outcome_when_attempts_run_out(*, had_unknown_outcome: bool) -> StepOutcome:
    return StepOutcome.REQUIRES_MANUAL_INTERVENTION if had_unknown_outcome else StepOutcome.FAILED


def escalated_outcome(*, outcome: StepOutcome, has_result: bool, kind: StepKind) -> StepOutcome:
    if is_uncompensatable_failure(outcome=outcome, has_result=has_result, kind=kind):
        return StepOutcome.REQUIRES_MANUAL_INTERVENTION
    if is_compensatable_success_without_result(outcome=outcome, has_result=has_result, kind=kind):
        return StepOutcome.REQUIRES_MANUAL_INTERVENTION
    return outcome


def is_uncompensatable_failure(*, outcome: StepOutcome, has_result: bool, kind: StepKind) -> bool:
    return outcome is StepOutcome.FAILED and has_result and kind is not StepKind.COMPENSATABLE


def is_compensatable_success_without_result(
    *, outcome: StepOutcome, has_result: bool, kind: StepKind
) -> bool:
    return outcome is StepOutcome.DONE and not has_result and kind is StepKind.COMPENSATABLE
