import logging
from collections.abc import Callable

from pydantic import JsonValue

from redis_enterprise_services.cluster.json_body import required_string_field
from redis_enterprise_services.cluster.read_again_polling import ReadAgainPolling
from redis_enterprise_services.cluster.status_goal import StatusGoal
from redis_enterprise_services.config.wait_settings import WaitSettings

logger: logging.Logger = logging.getLogger(name=__name__)


class StatusPolling:
    def __init__(self, *, read_again_polling: ReadAgainPolling, status_field: str) -> None:
        self._read_again_polling: ReadAgainPolling = read_again_polling
        self._status_field: str = status_field

    def wait_for[TRead](
        self,
        *,
        read: Callable[[], TRead],
        fields_of: Callable[[TRead], JsonValue],
        goal: StatusGoal[TRead],
        subject: str,
        wait: WaitSettings,
    ) -> TRead:
        last_read: list[TRead] = []

        def read_whether_done() -> bool:
            current: TRead = read()
            last_read[:] = [current]
            return self._is_done_or_raise_if_failed(
                status=self._status(fields=fields_of(current), subject=subject),
                current=current,
                goal=goal,
                subject=subject,
            )

        if self._read_again_polling.poll_until(is_done=read_whether_done, wait=wait, subject=subject):
            return last_read[-1]
        raise goal.timed_out()

    def _status(self, *, fields: JsonValue, subject: str) -> str:
        status: str = required_string_field(
            body=fields,
            name=self._status_field,
            missing_message=f"{subject} answered without {self._status_field}",
        )
        logger.debug(msg=f"{subject} is {status}")
        return status

    @staticmethod
    def _is_done_or_raise_if_failed[TRead](
        *, status: str, current: TRead, goal: StatusGoal[TRead], subject: str
    ) -> bool:
        if status in goal.failed_statuses:
            logger.warning(msg=f"{subject} ended as {status}")
            raise goal.failed(status, current)
        return status == goal.done_status
