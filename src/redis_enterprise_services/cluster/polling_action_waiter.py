import logging

from pydantic import JsonValue

from redis_enterprise_services.cluster.cluster_action_waiter import ClusterActionWaiter
from redis_enterprise_services.cluster.cluster_api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.json_body import string_field
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster.polling import poll_until_done_or_timeout
from redis_enterprise_services.cluster.safe_to_read_again import is_safe_to_read_again
from redis_enterprise_services.config.action_settings import ActionSettings
from redis_enterprise_services.config.cluster_api_settings import ClusterApiSettings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.cluster import (
    ClusterActionFailedError,
    ClusterActionTimeoutError,
    UnreadableClusterResponseError,
)

logger: logging.Logger = logging.getLogger(name=__name__)


class PollingActionWaiter(ClusterActionWaiter):
    def __init__(
        self,
        *,
        cluster_api_caller: ClusterApiCaller,
        settings: ActionSettings,
        cluster_api_settings: ClusterApiSettings,
    ) -> None:
        self._cluster_api_caller: ClusterApiCaller = cluster_api_caller
        self._settings: ActionSettings = settings
        self._cluster_api_settings: ClusterApiSettings = cluster_api_settings

    def wait_until_completed(self, *, target: ClusterTarget, action_uid: str | None) -> None:
        if action_uid is None:
            return
        if poll_until_done_or_timeout(
            wait_settings=self._settings.wait,
            is_done=lambda: self._read_whether_completed_or_raise_if_failed(
                target=target, action_uid=action_uid
            ),
        ):
            return
        raise ClusterActionTimeoutError(
            message=f"action {action_uid} did not complete in {self._settings.wait.timeout_seconds} seconds"
        )

    def _read_whether_completed_or_raise_if_failed(self, *, target: ClusterTarget, action_uid: str) -> bool:
        try:
            action_body: JsonValue = self._cluster_api_caller.send(
                target=target, method="GET", path=self._settings.item_path.format(uid=action_uid)
            ).body
        except RedisEnterpriseServicesError as error:
            if not is_safe_to_read_again(
                error=error, transient_error_codes=self._cluster_api_settings.transient_error_codes
            ):
                raise
            logger.warning(
                msg=f"reading action {action_uid} failed, it is read again: {error.coded_message()}"
            )
            return False
        status: str | None = string_field(body=action_body, name=self._cluster_api_settings.fields.status)
        if status is None:
            raise UnreadableClusterResponseError(message=f"action {action_uid} answered without a status")
        if status in self._settings.failed_statuses:
            raise ClusterActionFailedError(message=f"action {action_uid} ended as {status}: {action_body}")
        logger.debug(msg=f"action {action_uid} is {status}")
        return status == self._settings.completed_status
