from collections.abc import Callable

from redis_enterprise_services.cluster.read_again import ReadAgainReads
from redis_enterprise_services.config.wait_settings import WaitSettings
from redis_enterprise_services.timing.deadline_polling import DeadlinePolling


class ReadAgainPolling:
    def __init__(self, *, deadline_polling: DeadlinePolling, transient_error_codes: frozenset[str]) -> None:
        self._deadline_polling: DeadlinePolling = deadline_polling
        self._transient_error_codes: frozenset[str] = transient_error_codes

    def poll_until(self, *, is_done: Callable[[], bool], wait: WaitSettings, subject: str) -> bool:
        reads: ReadAgainReads = ReadAgainReads(
            is_done=is_done, transient_error_codes=self._transient_error_codes, subject=subject
        )
        done: bool = self._deadline_polling.poll_until(
            is_done=reads.is_done_or_read_again,
            timeout_seconds=wait.timeout_seconds,
            poll_interval_seconds=wait.poll_interval_seconds,
        )
        if not done:
            reads.raise_last_error_if_no_read_succeeded()
        return done
