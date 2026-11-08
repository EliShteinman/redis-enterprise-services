from collections.abc import Callable

from redis_enterprise_services.cluster.read_again import tolerate_read_again_errors
from redis_enterprise_services.config.wait_settings import WaitSettings
from redis_enterprise_services.timing.deadline_polling import DeadlinePolling


class ReadAgainPolling:
    def __init__(self, *, deadline_polling: DeadlinePolling, transient_error_codes: frozenset[str]) -> None:
        self._deadline_polling: DeadlinePolling = deadline_polling
        self._transient_error_codes: frozenset[str] = transient_error_codes

    def poll_until(self, *, is_done: Callable[[], bool], wait: WaitSettings, subject: str) -> bool:
        return self._deadline_polling.poll_until(
            is_done=tolerate_read_again_errors(
                is_done=is_done, transient_error_codes=self._transient_error_codes, subject=subject
            ),
            timeout_seconds=wait.timeout_seconds,
            poll_interval_seconds=wait.poll_interval_seconds,
        )
