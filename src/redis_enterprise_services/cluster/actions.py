import logging

from pydantic import JsonValue

from redis_enterprise_services.cluster.action_tracker import ActionTracker
from redis_enterprise_services.cluster.caller import ClusterCaller
from redis_enterprise_services.cluster.json_body import string_field
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster.polling import poll_until
from redis_enterprise_services.config.action_settings import ActionSettings
from redis_enterprise_services.config.cluster_settings import ClusterSettings
from redis_enterprise_services.exceptions.cluster import (
    ClusterActionFailedError,
    ClusterActionTimeoutError,
    ClusterRequestError,
    UnreadableAnswerError,
)
from redis_enterprise_services.exceptions.edge import (
    OutcomeUnknownError,
    RequestNotSentError,
    ResponseRejectedError,
)

logger: logging.Logger = logging.getLogger(name=__name__)


class ActionWaiter(ActionTracker):
    def __init__(self, *, api: ClusterCaller, settings: ActionSettings, cluster: ClusterSettings) -> None:
        self._api: ClusterCaller = api
        self._settings: ActionSettings = settings
        self._cluster: ClusterSettings = cluster

    def wait(self, *, target: ClusterTarget, action_uid: str | None) -> None:
        if action_uid is None:
            return
        if poll_until(
            wait=self._settings.wait, is_done=lambda: self._is_completed(target=target, action_uid=action_uid)
        ):
            return
        raise ClusterActionTimeoutError(
            message=f"action {action_uid} did not complete in {self._settings.wait.timeout_seconds} seconds"
        )

    def _is_completed(self, *, target: ClusterTarget, action_uid: str) -> bool:
        try:
            action: JsonValue = self._api.send(
                target=target, method="GET", path=self._settings.path.format(uid=action_uid)
            ).body
        except (RequestNotSentError, OutcomeUnknownError, ResponseRejectedError) as error:
            logger.warning(msg=f"reading action {action_uid} failed, it is read again: {error.describe()}")
            return False
        except ClusterRequestError as error:
            if error.error_code not in self._cluster.transient_error_codes:
                raise
            logger.warning(msg=f"the cluster is busy reading action {action_uid}, it is read again")
            return False
        status: str | None = string_field(body=action, name=self._cluster.fields.status)
        if status is None:
            raise UnreadableAnswerError(message=f"action {action_uid} answered without a status")
        if status in self._settings.failed_statuses:
            raise ClusterActionFailedError(message=f"action {action_uid} ended as {status}: {action}")
        logger.debug(msg=f"action {action_uid} is {status}")
        return status == self._settings.completed_status
