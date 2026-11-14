import logging

from pydantic import JsonValue

from redis_enterprise_services.cluster.cluster_api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.json_body import string_field
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster.status_goal import StatusGoal
from redis_enterprise_services.cluster.status_polling import StatusPolling
from redis_enterprise_services.config.crdb_settings import CrdbTaskSettings
from redis_enterprise_services.exceptions.cluster import CrdbTaskFailedError, CrdbTaskTimeoutError

logger: logging.Logger = logging.getLogger(name=__name__)


class CrdbTaskWaiter:
    def __init__(
        self,
        *,
        cluster_api_caller: ClusterApiCaller,
        status_polling: StatusPolling,
        settings: CrdbTaskSettings,
    ) -> None:
        self._cluster_api_caller: ClusterApiCaller = cluster_api_caller
        self._status_polling: StatusPolling = status_polling
        self._settings: CrdbTaskSettings = settings

    def wait_until_finished(self, *, target: ClusterTarget, task_id: str) -> JsonValue:
        return self._status_polling.wait_for(
            read=lambda: self.read_task(target=target, task_id=task_id),
            fields_of=task_fields,
            goal=self._finished_goal(task_id=task_id),
            subject=f"CRDB task {task_id}",
            wait=self._settings.wait,
        )

    def read_task(self, *, target: ClusterTarget, task_id: str) -> JsonValue:
        return self._cluster_api_caller.send(
            target=target, method="GET", path=self._settings.item_path.format(uid=task_id)
        ).body

    def _finished_goal(self, *, task_id: str) -> StatusGoal[JsonValue]:
        return StatusGoal[JsonValue](
            done_status=self._settings.completed_status,
            failed_statuses=self._settings.failed_statuses,
            failed=lambda status, task_body: self._task_failed(
                task_id=task_id, status=status, task_body=task_body
            ),
            timed_out=lambda: CrdbTaskTimeoutError(
                message=f"CRDB task {task_id} did not finish in {self._settings.wait.timeout_seconds} seconds"
            ),
        )

    def _task_failed(self, *, task_id: str, status: str, task_body: JsonValue) -> CrdbTaskFailedError:
        logger.info(msg=f"the body of {status} CRDB task {task_id}: {task_body}")
        first_error: JsonValue = first_item(body=task_body, name=self._settings.errors_field)
        cluster_name: str | None = string_field(body=first_error, name=self._settings.error_cluster_field)
        error_code: str | None = string_field(body=first_error, name=self._settings.error_code_field)
        place: str = "" if cluster_name is None else f" on {cluster_name}"
        reason: str = "" if error_code is None else f" ({error_code})"
        return CrdbTaskFailedError(
            message=f"CRDB task {task_id} ended as {status}{place}{reason}", cluster_error_code=error_code
        )


def first_item(*, body: JsonValue, name: str) -> JsonValue:
    items: JsonValue = body.get(name) if isinstance(body, dict) else None
    return items[0] if isinstance(items, list) and items else None


def task_fields(task_body: JsonValue) -> JsonValue:
    return task_body
