from pydantic import JsonValue

from redis_enterprise_services.cluster.cluster_action_waiter import ClusterActionWaiter
from redis_enterprise_services.cluster.cluster_api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster.status_goal import StatusGoal
from redis_enterprise_services.cluster.status_polling import StatusPolling
from redis_enterprise_services.config.action_settings import ActionSettings
from redis_enterprise_services.exceptions.cluster import (
    ClusterActionFailedError,
    ClusterActionTimeoutError,
)


class PollingActionWaiter(ClusterActionWaiter):
    def __init__(
        self, *, cluster_api_caller: ClusterApiCaller, status_polling: StatusPolling, settings: ActionSettings
    ) -> None:
        self._cluster_api_caller: ClusterApiCaller = cluster_api_caller
        self._status_polling: StatusPolling = status_polling
        self._settings: ActionSettings = settings

    def wait_until_completed(self, *, target: ClusterTarget, action_uid: str | None) -> JsonValue:
        if action_uid is None:
            return None
        return self._status_polling.wait_for(
            read=lambda: self._read_action_body(target=target, action_uid=action_uid),
            fields_of=action_fields,
            goal=self._completion_goal(action_uid=action_uid),
            subject=f"action {action_uid}",
            wait=self._settings.wait,
        )

    def _completion_goal(self, *, action_uid: str) -> StatusGoal[JsonValue]:
        return StatusGoal[JsonValue](
            done_status=self._settings.completed_status,
            failed_statuses=self._settings.failed_statuses,
            failed=lambda status, action_body: ClusterActionFailedError(
                message=f"action {action_uid} ended as {status}: {action_body}"
            ),
            timed_out=lambda: ClusterActionTimeoutError(
                message=f"action {action_uid} did not complete "
                f"in {self._settings.wait.timeout_seconds} seconds"
            ),
        )

    def _read_action_body(self, *, target: ClusterTarget, action_uid: str) -> JsonValue:
        return self._cluster_api_caller.send(
            target=target, method="GET", path=self._settings.item_path.format(uid=action_uid)
        ).body


def action_fields(action_body: JsonValue) -> JsonValue:
    return action_body
