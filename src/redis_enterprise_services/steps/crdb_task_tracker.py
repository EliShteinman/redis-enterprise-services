import logging
from collections.abc import Callable

from pydantic import JsonValue

from redis_enterprise_services.cluster.crdb_task_waiter import CrdbTaskWaiter
from redis_enterprise_services.cluster.json_body import required_string_field
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster.rejection_kind import is_not_found
from redis_enterprise_services.config.crdb_settings import CrdbTaskSettings
from redis_enterprise_services.exceptions.cluster import (
    ClusterRejectedRequestError,
    CrdbTaskFailedError,
    CrdbTaskTimeoutError,
)

logger: logging.Logger = logging.getLogger(name=__name__)


class CrdbTaskTracker:
    def __init__(self, *, task_waiter: CrdbTaskWaiter, settings: CrdbTaskSettings, status_field: str) -> None:
        self._task_waiter: CrdbTaskWaiter = task_waiter
        self._settings: CrdbTaskSettings = settings
        self._status_field: str = status_field

    def send_or_join(self, *, send: Callable[[], None], task_id: str) -> None:
        try:
            send()
        except ClusterRejectedRequestError as error:
            if error.cluster_error_code != self._settings.existing_task_error_code:
                raise
            logger.info(msg=f"CRDB task {task_id} already reached the cluster, waiting for it")

    def wait_until_finished(self, *, target: ClusterTarget, task_id: str) -> JsonValue:
        return self._task_waiter.wait_until_finished(target=target, task_id=task_id)

    def task_or_none(self, *, target: ClusterTarget, task_id: str) -> JsonValue | None:
        try:
            return self._task_waiter.read_task(target=target, task_id=task_id)
        except ClusterRejectedRequestError as error:
            if not is_not_found(error=error):
                raise
            logger.info(msg=f"CRDB task {task_id} is unknown to the cluster")
            return None

    def status_of(self, *, task: JsonValue) -> str:
        return required_string_field(
            body=task,
            name=self._status_field,
            missing_message=f"a CRDB task answered without {self._status_field}",
        )

    def is_finished(self, *, task: JsonValue) -> bool:
        return self.status_of(task=task) == self._settings.completed_status

    def has_failed(self, *, task: JsonValue) -> bool:
        return self.status_of(task=task) in self._settings.failed_statuses

    def is_running(self, *, task: JsonValue) -> bool:
        return not self.is_finished(task=task) and not self.has_failed(task=task)

    def reject_an_unfinished_task(self, *, target: ClusterTarget, task: JsonValue, task_id: str) -> None:
        if self.is_running(task=task):
            raise CrdbTaskTimeoutError(message=f"CRDB task {task_id} is still {self.status_of(task=task)}")
        if self.has_failed(task=task):
            self._task_waiter.wait_until_finished(target=target, task_id=task_id)

    def settle(self, *, target: ClusterTarget, task_id: str) -> None:
        task: JsonValue | None = self.task_or_none(target=target, task_id=task_id)
        if task is None or not self.is_running(task=task):
            return
        logger.info(msg=f"waiting for CRDB task {task_id} to end before deciding")
        try:
            self._task_waiter.wait_until_finished(target=target, task_id=task_id)
        except CrdbTaskFailedError:
            logger.info(msg=f"CRDB task {task_id} ended without applying its change")
