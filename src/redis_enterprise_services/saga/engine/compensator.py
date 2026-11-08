import logging

from redis_enterprise_services.config.saga_settings import SagaSettings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.saga.contract.failure import FailureCategory, FailureClassifier
from redis_enterprise_services.saga.contract.saga_record import ObtainedBy, StepError
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.saga.engine.backoff import wait_before_retry
from redis_enterprise_services.saga.engine.step_recorder import StepRecorder
from redis_enterprise_services.saga.plan.step_protocols import PreparedStep
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
        all_compensated: bool = True
        for step, recorder in reversed(prepared_steps):
            if step.kind is not StepKind.COMPENSATABLE or not step.has_result:
                continue
            all_compensated = self._compensate_step(step=step, recorder=recorder) and all_compensated
        return all_compensated

    def _compensate_step(self, *, step: PreparedStep, recorder: StepRecorder) -> bool:
        if step.obtained_by is ObtainedBy.FOUND:
            logger.warning(
                msg=f"compensating {step.key}, which was found by find_outcome, not kept by execute, "
                "and may not be ours"
            )
        recorder.mark_compensating()
        last_error: StepError | None = self._compensate_with_retries(step=step)
        if last_error is None:
            logger.info(msg=f"step {step.key} compensated")
            recorder.mark_compensated()
            return True
        logger.error(msg=f"compensation of {step.key} gave up: {last_error.code}: {last_error.message}")
        recorder.mark_compensation_failed(error=last_error)
        return False

    def _compensate_with_retries(self, *, step: PreparedStep) -> StepError | None:
        attempts: int = self._settings.compensation_retry.attempts
        last_error: StepError | None = None
        for attempt in range(1, attempts + 1):
            try:
                step.compensate()
            except RedisEnterpriseServicesError as error:
                last_error = StepError.from_exception(error=error)
                logger.warning(msg=f"a compensation attempt of {step.key} failed: {error.coded_message()}")
                if self._classifier.classify_step_error(error=error) not in RETRIED_COMPENSATION_FAILURES:
                    return last_error
                if attempt < attempts:
                    wait_before_retry(
                        retry_settings=self._settings.compensation_retry,
                        attempt=attempt,
                        sleeper=self._sleeper,
                    )
                continue
            return None
        return last_error
