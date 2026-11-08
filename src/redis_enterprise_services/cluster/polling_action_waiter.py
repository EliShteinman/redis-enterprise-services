import logging

from pydantic import JsonValue

from redis_enterprise_services.cluster.cluster_action_waiter import ClusterActionWaiter
from redis_enterprise_services.cluster.cluster_api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.json_body import string_field
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster.read_again import tolerate_read_again_errors
from redis_enterprise_services.config.action_settings import ActionSettings
from redis_enterprise_services.config.cluster_api_settings import ClusterApiSettings
from redis_enterprise_services.exceptions.cluster import (
    ClusterActionFailedError,
    ClusterActionTimeoutError,
    UnreadableClusterResponseError,
)
from redis_enterprise_services.timing.deadline_polling import DeadlinePolling

logger: logging.Logger = logging.getLogger(name=__name__)


class PollingActionWaiter(ClusterActionWaiter):
    def __init__(
        self,
        *,
        cluster_api_caller: ClusterApiCaller,
        deadline_polling: DeadlinePolling,
        settings: ActionSettings,
        cluster_api_settings: ClusterApiSettings,
    ) -> None:
        self._cluster_api_caller: ClusterApiCaller = cluster_api_caller
        self._deadline_polling: DeadlinePolling = deadline_polling
        self._settings: ActionSettings = settings
        self._cluster_api_settings: ClusterApiSettings = cluster_api_settings

    def wait_until_completed(self, *, target: ClusterTarget, action_uid: str | None) -> None:
        if action_uid is None:
            return
        if self._deadline_polling.poll_until(
            is_done=tolerate_read_again_errors(
                is_done=lambda: self._read_whether_completed_or_raise_if_failed(
                    target=target, action_uid=action_uid
                ),
                transient_error_codes=self._cluster_api_settings.transient_error_codes,
                subject=f"action {action_uid}",
            ),
            timeout_seconds=self._settings.wait.timeout_seconds,
            poll_interval_seconds=self._settings.wait.poll_interval_seconds,
        ):
            return
        raise ClusterActionTimeoutError(
            message=f"action {action_uid} did not complete in {self._settings.wait.timeout_seconds} seconds"
        )

    def _read_whether_completed_or_raise_if_failed(self, *, target: ClusterTarget, action_uid: str) -> bool:
        action_body: JsonValue = self._read_action_body(target=target, action_uid=action_uid)
        status: str = required_action_status(
            action_uid=action_uid,
            action_body=action_body,
            status_field=self._cluster_api_settings.fields.status,
        )
        logger.debug(msg=f"action {action_uid} is {status}")
        return is_completed_or_raise_if_failed(
            action_uid=action_uid, status=status, action_body=action_body, settings=self._settings
        )

    def _read_action_body(self, *, target: ClusterTarget, action_uid: str) -> JsonValue:
        return self._cluster_api_caller.send(
            target=target, method="GET", path=self._settings.item_path.format(uid=action_uid)
        ).body


def required_action_status(*, action_uid: str, action_body: JsonValue, status_field: str) -> str:
    status: str | None = string_field(body=action_body, name=status_field)
    if status is None:
        raise UnreadableClusterResponseError(message=f"action {action_uid} answered without a status")
    return status


def is_completed_or_raise_if_failed(
    *, action_uid: str, status: str, action_body: JsonValue, settings: ActionSettings
) -> bool:
    if status in settings.failed_statuses:
        raise ClusterActionFailedError(message=f"action {action_uid} ended as {status}: {action_body}")
    return status == settings.completed_status
