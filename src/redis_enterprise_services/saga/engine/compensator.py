import logging

from redis_enterprise_services.config.saga_settings import SagaSettings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.saga.contract.failure import FailureCategory, FailureClassifier
from redis_enterprise_services.saga.contract.saga_record import ObtainedBy, StepError
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.saga.engine.step_recorder import StepRecorder
from redis_enterprise_services.saga.plan.step_protocols import PreparedStep
from redis_enterprise_services.timing.paced_attempts import paced_attempts
from redis_enterprise_services.timing.sleeper import Sleeper

logger: logging.Logger = logging.getLogger(name=__name__)


RETRIED_COMPENSATION_FAILURES: frozenset[FailureCategory] = frozenset(
    {FailureCategory.TRANSIENT, FailureCategory.OUTCOME_UNKNOWN}
)


class Compensator:
    def __init__(self, *, settings: SagaSettings, classifier: FailureClassifier, sleeper: Sleeper) -> None:
        self._settings: SagaSettings = settings
        self._classifier: FailureClassifier = classifier
        self._sleeper: Sleeper = sleeper

    def compensate_in_reverse(self, *, prepared_steps: list[tuple[PreparedStep, StepRecorder]]) -> bool:
        return all(
            [
                self._compensate_step(step=step, recorder=recorder)
                for step, recorder in steps_to_compensate(prepared_steps=prepared_steps)
            ]
        )

    def _compensate_step(self, *, step: PreparedStep, recorder: StepRecorder) -> bool:
        warn_if_found_not_kept(step=step)
        recorder.mark_compensating()
        last_error: StepError | None = self._compensate_with_retries(step=step)
        return mark_compensation_end(step=step, recorder=recorder, last_error=last_error)

    def _compensate_with_retries(self, *, step: PreparedStep) -> StepError | None:
        last_error: RedisEnterpriseServicesError | None = None
        for _attempt in paced_attempts(
            attempts=self._settings.compensation_retry.attempts,
            backoff_step_seconds=self._settings.compensation_retry.backoff_step_seconds,
            sleeper=self._sleeper,
        ):
            last_error = self._compensate_once(step=step)
            if last_error is None or not self._is_retried(error=last_error):
                break
        return None if last_error is None else StepError.from_exception(error=last_error)

    def _compensate_once(self, *, step: PreparedStep) -> RedisEnterpriseServicesError | None:
        try:
            step.compensate()
        except RedisEnterpriseServicesError as error:
            logger.warning(msg=f"a compensation attempt of {step.key} failed: {error.coded_message()}")
            return error
        return None

    def _is_retried(self, *, error: RedisEnterpriseServicesError) -> bool:
        return self._classifier.classify_step_error(error=error) in RETRIED_COMPENSATION_FAILURES


def steps_to_compensate(
    *, prepared_steps: list[tuple[PreparedStep, StepRecorder]]
) -> list[tuple[PreparedStep, StepRecorder]]:
    return [
        (step, recorder)
        for step, recorder in reversed(prepared_steps)
        if step.kind is StepKind.COMPENSATABLE and step.has_result
    ]


def warn_if_found_not_kept(*, step: PreparedStep) -> None:
    if step.obtained_by is ObtainedBy.FOUND:
        logger.warning(
            msg=f"compensating {step.key}, which was found by find_outcome, not kept by execute, "
            "and may not be ours"
        )


def mark_compensation_end(
    *, step: PreparedStep, recorder: StepRecorder, last_error: StepError | None
) -> bool:
    if last_error is None:
        logger.info(msg=f"step {step.key} compensated")
        recorder.mark_compensated()
        return True
    logger.error(msg=f"compensation of {step.key} gave up: {last_error.code}: {last_error.message}")
    recorder.mark_compensation_failed(error=last_error)
    return False
