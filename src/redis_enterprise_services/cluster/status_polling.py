from collections.abc import Callable

from pydantic import JsonValue

from redis_enterprise_services.cluster.read_again_polling import ReadAgainPolling
from redis_enterprise_services.cluster.status_goal import StatusGoal
from redis_enterprise_services.cluster.status_reader import StatusReader
from redis_enterprise_services.config.wait_settings import WaitSettings


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
        reader: StatusReader[TRead] = StatusReader(
            read=read, fields_of=fields_of, goal=goal, status_field=self._status_field, subject=subject
        )
        if not self._read_again_polling.poll_until(is_done=reader.is_done, wait=wait, subject=subject):
            raise goal.timed_out()
        return reader.last_read()
