import logging
from collections.abc import Callable

from pydantic import JsonValue

from redis_enterprise_services.cluster.json_body import required_string_field
from redis_enterprise_services.cluster.status_goal import StatusGoal
from redis_enterprise_services.exceptions.cluster import UnreadableClusterResponseError

logger: logging.Logger = logging.getLogger(name=__name__)


class StatusReader[TRead]:
    def __init__(
        self,
        *,
        read: Callable[[], TRead],
        fields_of: Callable[[TRead], JsonValue],
        goal: StatusGoal[TRead],
        status_field: str,
        subject: str,
    ) -> None:
        self._read: Callable[[], TRead] = read
        self._fields_of: Callable[[TRead], JsonValue] = fields_of
        self._goal: StatusGoal[TRead] = goal
        self._status_field: str = status_field
        self._subject: str = subject
        self._last_read: tuple[TRead] | None = None

    def is_done(self) -> bool:
        current: TRead = self._read()
        self._last_read = (current,)
        status: str = self._status(fields=self._fields_of(current))
        if status in self._goal.failed_statuses:
            logger.warning(msg=f"{self._subject} ended as {status}")
            raise self._goal.failed(status, current)
        return status == self._goal.done_status

    def last_read(self) -> TRead:
        if self._last_read is None:
            raise UnreadableClusterResponseError(message=f"{self._subject} was never read")
        return self._last_read[0]

    def _status(self, *, fields: JsonValue) -> str:
        status: str = required_string_field(
            body=fields,
            name=self._status_field,
            missing_message=f"{self._subject} answered without {self._status_field}",
        )
        logger.debug(msg=f"{self._subject} is {status}")
        return status
