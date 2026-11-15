import pytest
from pydantic import ValidationError

from redis_enterprise_services.config.crdb_settings import CrdbTaskSettings

TASK: dict[str, object] = {
    "item_path": "/v1/crdb_tasks/{uid}",
    "id_field": "id",
    "completed_status": "finished",
    "failed_statuses": ["failed"],
    "guid_field": "crdb_guid",
    "existing_task_error_code": "job_exists",
    "errors_field": "errors",
    "error_cluster_field": "cluster_name",
    "error_code_field": "error_code",
    "wait": {"poll_interval_seconds": 2, "timeout_seconds": 600},
}


def test_a_task_result_kept_no_longer_than_the_wait_is_refused() -> None:
    with pytest.raises(expected_exception=ValidationError):
        CrdbTaskSettings.model_validate({**TASK, "result_ttl_seconds": 600})


def test_a_task_result_kept_longer_than_the_wait_is_accepted() -> None:
    assert CrdbTaskSettings.model_validate({**TASK, "result_ttl_seconds": 601}).result_ttl_seconds == 601


def test_a_completed_status_that_is_also_failed_is_refused() -> None:
    with pytest.raises(expected_exception=ValidationError):
        CrdbTaskSettings.model_validate({**TASK, "result_ttl_seconds": 601, "failed_statuses": ["finished"]})
