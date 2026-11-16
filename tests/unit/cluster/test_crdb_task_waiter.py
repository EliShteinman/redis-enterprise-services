from pathlib import Path
from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.cluster_api_caller import ClusterApiCaller
from redis_enterprise_services.cluster.crdb_task_waiter import CrdbTaskWaiter
from redis_enterprise_services.cluster.models import ClusterTarget, SuccessfulClusterResponse
from redis_enterprise_services.cluster.read_again_polling import ReadAgainPolling
from redis_enterprise_services.cluster.status_polling import StatusPolling
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.settings import Settings, load_settings
from redis_enterprise_services.config.wait_settings import WaitSettings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError
from redis_enterprise_services.exceptions.cluster import CrdbTaskFailedError, CrdbTaskTimeoutError
from redis_enterprise_services.timing.clock import Clock
from redis_enterprise_services.timing.deadline_polling import DeadlinePolling
from redis_enterprise_services.timing.sleeper import Sleeper

TARGET: ClusterTarget = ClusterTarget(
    network="local",
    api_url="https://cluster.local:9443",
    credentials=ClusterCredentials(username="admin", password=SecretStr("secret")),
)
TASK_ID: str = "16a0c036-6d3a-4ad0-9352-a56108ea8138"
FAILED_TASK: JsonValue = {
    "status": "failed",
    "errors": [
        {
            "cluster_name": "cluster2.local",
            "description": "Unavailable or invalid port (status code 406)",
            "error_code": "db_create_failed",
        }
    ],
}


class SimulatedTime(Clock, Sleeper):
    def __init__(self) -> None:
        self._now: float = 0.0

    def monotonic_seconds(self) -> float:
        return self._now

    def sleep(self, *, seconds: float) -> None:
        self._now += seconds


@pytest.fixture
def settings(config_dir: Path) -> Settings:
    return load_settings(config_dir=config_dir)


def waiter_answering(*, task_body: JsonValue, settings: Settings) -> CrdbTaskWaiter:
    api: MagicMock = create_autospec(spec=ClusterApiCaller, instance=True)
    api.send.return_value = SuccessfulClusterResponse(body=task_body, cluster_state_id=None)
    simulated_time: SimulatedTime = SimulatedTime()
    return CrdbTaskWaiter(
        cluster_api_caller=api,
        status_polling=StatusPolling(
            read_again_polling=ReadAgainPolling(
                deadline_polling=DeadlinePolling(clock=simulated_time, sleeper=simulated_time),
                transient_error_codes=settings.cluster_api.transient_error_codes,
            ),
            status_field=settings.cluster_api.fields.status,
        ),
        settings=settings.crdb.task.model_copy(
            update={"wait": WaitSettings(poll_interval_seconds=1, timeout_seconds=10)}
        ),
    )


def test_a_finished_task_is_returned(settings: Settings) -> None:
    finished: JsonValue = {"status": "finished", "crdb_guid": "d71cefce-4e31-41fd-b654-37cbb2f39a01"}

    assert (
        waiter_answering(task_body=finished, settings=settings).wait_until_finished(
            target=TARGET, task_id=TASK_ID
        )
        == finished
    )


def test_a_task_failed_on_the_polled_cluster_keeps_its_error_code(settings: Settings) -> None:
    failed_here: JsonValue = {
        "status": "failed",
        "errors": [{"cluster_name": "Cluster.local", "error_code": "db_create_failed"}],
    }

    with pytest.raises(expected_exception=CrdbTaskFailedError) as failure:
        waiter_answering(task_body=failed_here, settings=settings).wait_until_finished(
            target=TARGET, task_id=TASK_ID
        )

    assert failure.value.cluster_error_code == "db_create_failed"


def test_a_task_failed_on_another_site_gives_no_error_code_for_the_polled_cluster(settings: Settings) -> None:
    with pytest.raises(expected_exception=CrdbTaskFailedError) as failure:
        waiter_answering(task_body=FAILED_TASK, settings=settings).wait_until_finished(
            target=TARGET, task_id=TASK_ID
        )

    assert failure.value.cluster_error_code is None


def test_a_failed_task_names_the_site_and_not_the_description(settings: Settings) -> None:
    with pytest.raises(expected_exception=CrdbTaskFailedError) as failure:
        waiter_answering(task_body=FAILED_TASK, settings=settings).wait_until_finished(
            target=TARGET, task_id=TASK_ID
        )

    assert (
        failure.value.message == f"CRDB task {TASK_ID} ended as failed on cluster2.local (db_create_failed)"
    )


def test_a_task_that_never_finishes_times_out(settings: Settings) -> None:
    with pytest.raises(expected_exception=CrdbTaskTimeoutError):
        waiter_answering(task_body={"status": "started"}, settings=settings).wait_until_finished(
            target=TARGET, task_id=TASK_ID
        )


def test_a_task_canceled_without_errors_still_fails_with_its_status(settings: Settings) -> None:
    with pytest.raises(expected_exception=CrdbTaskFailedError) as failure:
        waiter_answering(task_body={"status": "canceled"}, settings=settings).wait_until_finished(
            target=TARGET, task_id=TASK_ID
        )

    assert failure.value.message == f"CRDB task {TASK_ID} ended as canceled"


def test_every_failing_site_is_named(settings: Settings) -> None:
    failed_on_two: JsonValue = {
        "status": "failed",
        "errors": [
            {"cluster_name": "cluster1.local", "error_code": "db_create_failed"},
            {"cluster_name": "cluster2.local", "error_code": "busy"},
        ],
    }

    with pytest.raises(expected_exception=CrdbTaskFailedError) as failure:
        waiter_answering(task_body=failed_on_two, settings=settings).wait_until_finished(
            target=TARGET, task_id=TASK_ID
        )

    assert "cluster1.local (db_create_failed), cluster2.local (busy)" in failure.value.message


@pytest.mark.parametrize(
    argnames="task_body", argvalues=[FAILED_TASK, {"status": "started"}, {"crdb_guid": "g"}]
)
def test_a_task_that_ends_badly_names_the_cluster_it_was_read_from(
    task_body: JsonValue, settings: Settings
) -> None:
    with pytest.raises(expected_exception=RedisEnterpriseServicesError) as failure:
        waiter_answering(task_body=task_body, settings=settings).wait_until_finished(
            target=TARGET, task_id=TASK_ID
        )

    assert failure.value.cluster_url == TARGET.api_url


def test_the_polled_cluster_keeps_its_error_code_when_another_site_failed_too(settings: Settings) -> None:
    failed_on_two: JsonValue = {
        "status": "failed",
        "errors": [
            {"cluster_name": "cluster.local", "error_code": "db_create_failed"},
            {"cluster_name": "cluster2.local", "error_code": "busy"},
        ],
    }

    with pytest.raises(expected_exception=CrdbTaskFailedError) as failure:
        waiter_answering(task_body=failed_on_two, settings=settings).wait_until_finished(
            target=TARGET, task_id=TASK_ID
        )

    assert failure.value.cluster_error_code == "db_create_failed"
