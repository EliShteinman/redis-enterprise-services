import logging
import time

from pydantic import JsonValue

from redis_enterprise_services.cluster.api import ClusterApi
from redis_enterprise_services.config.action_settings import ActionSettings
from redis_enterprise_services.edge.models import ClusterTarget
from redis_enterprise_services.exceptions.cluster import ClusterActionFailedError, ClusterActionTimeoutError

STATUS_FIELD: str = "status"

logger: logging.Logger = logging.getLogger(name=__name__)


class ActionWaiter:
    def __init__(self, *, api: ClusterApi, settings: ActionSettings) -> None:
        self._api: ClusterApi = api
        self._settings: ActionSettings = settings

    def wait(self, *, target: ClusterTarget, action_uid: str) -> None:
        deadline: float = time.monotonic() + self._settings.wait.timeout_seconds
        while time.monotonic() < deadline:
            action: JsonValue = self._api.send(
                target=target, method="GET", path=self._settings.path.format(uid=action_uid)
            ).body
            status: JsonValue = action.get(STATUS_FIELD) if isinstance(action, dict) else None
            if status == self._settings.completed_status:
                return
            if status == self._settings.failed_status:
                raise ClusterActionFailedError(message=f"action {action_uid} failed: {action}")
            logger.debug(msg=f"action {action_uid} is {status}")
            time.sleep(self._settings.wait.interval_seconds)
        raise ClusterActionTimeoutError(
            message=f"action {action_uid} did not complete in {self._settings.wait.timeout_seconds} seconds"
        )
