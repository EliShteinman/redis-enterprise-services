from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.cluster_target_resolver import SharedCredentialsTargetResolver
from redis_enterprise_services.cluster.crdb_task_waiter import CrdbTaskWaiter
from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.settings import load_settings
from redis_enterprise_services.crdbs.repository import CrdbRepository
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.exceptions.cluster import ClusterRejectedRequestError, CrdbTaskTimeoutError
from redis_enterprise_services.steps.crdb_task_tracker import CrdbTaskTracker
from redis_enterprise_services.steps.create_crdb import CreateCrdbInput, CreateCrdbStep, CreatedCrdb

GUID: str = "d71cefce-4e31-41fd-b654-37cbb2f39a01"
STEP_INPUT: CreateCrdbInput = CreateCrdbInput(
    coordinator=ClusterAddress(network="net-a", api_url="https://cluster-a:9443"),
    members=[
        ClusterAddress(network="net-a", api_url="https://cluster-a:9443"),
        ClusterAddress(network="net-a", api_url="https://cluster-b:9443"),
    ],
    database=NewDatabase(name="orders", memory_size=104857600),
    task_id="16a0c036-6d3a-4ad0-9352-a56108ea8138",
)
NOT_FOUND: ClusterRejectedRequestError = ClusterRejectedRequestError(
    message="m", cluster_status_code=404, cluster_error_code="not_found"
)


class StepHarness:
    def __init__(self) -> None:
        self.repository: MagicMock = create_autospec(spec=CrdbRepository, instance=True)
        self.task_waiter: MagicMock = create_autospec(spec=CrdbTaskWaiter, instance=True)
        self.kept: list[CreatedCrdb] = []
        self.step: CreateCrdbStep = CreateCrdbStep(
            repository=self.repository,
            task_tracker=CrdbTaskTracker(
                task_waiter=self.task_waiter, settings=load_settings().crdb.task, status_field="status"
            ),
            target_resolver=SharedCredentialsTargetResolver(
                credentials=ClusterCredentials(username="admin", password=SecretStr("secret"))
            ),
            guid_field="crdb_guid",
            new_task_id=lambda: "delete-task",
        )

    def find_outcome_with_task(self, *, task: JsonValue | Exception) -> CreatedCrdb | None:
        if isinstance(task, Exception):
            self.task_waiter.read_task.side_effect = task
        else:
            self.task_waiter.read_task.return_value = task
        return self.step.find_outcome(
            step_input=STEP_INPUT,
            kept_result=None,
            keep_result_if_none_kept=self.keep,
        )

    def keep(self, result: CreatedCrdb) -> None:
        self.kept.append(result)


def test_a_finished_creation_keeps_the_guid_of_its_task() -> None:
    harness: StepHarness = StepHarness()
    harness.task_waiter.wait_until_finished.return_value = {"status": "finished", "crdb_guid": GUID}

    harness.step.execute(step_input=STEP_INPUT, keep_result=harness.keep)

    assert harness.kept == [CreatedCrdb(guid=GUID)]


@pytest.mark.parametrize(
    argnames="task",
    argvalues=[
        pytest.param(NOT_FOUND, id="task-never-arrived"),
        pytest.param({"status": "failed"}, id="failed"),
    ],
)
def test_a_creation_whose_task_never_ran_or_failed_left_nothing(task: JsonValue | Exception) -> None:
    assert StepHarness().find_outcome_with_task(task=task) is None


def test_a_creation_whose_task_finished_is_found_by_our_task_id() -> None:
    found: CreatedCrdb | None = StepHarness().find_outcome_with_task(
        task={"status": "finished", "crdb_guid": GUID}
    )

    assert found == CreatedCrdb(guid=GUID)


def test_a_creation_whose_task_is_still_running_is_not_cancelled_but_left_unknown() -> None:
    with pytest.raises(expected_exception=CrdbTaskTimeoutError):
        StepHarness().find_outcome_with_task(task={"status": "started"})


def test_deleting_a_crdb_that_is_already_gone_is_done() -> None:
    harness: StepHarness = StepHarness()
    harness.repository.start_deletion.side_effect = NOT_FOUND

    harness.step.compensate(step_input=STEP_INPUT, result=CreatedCrdb(guid=GUID))

    harness.task_waiter.wait_until_finished.assert_not_called()


def test_a_creation_sent_again_joins_the_task_that_already_reached_the_cluster() -> None:
    harness: StepHarness = StepHarness()
    harness.repository.start_creation.side_effect = ClusterRejectedRequestError(
        message="m", cluster_status_code=406, cluster_error_code="job_exists"
    )
    harness.task_waiter.wait_until_finished.return_value = {"status": "finished", "crdb_guid": GUID}

    harness.step.execute(step_input=STEP_INPUT, keep_result=harness.keep)

    assert harness.kept == [CreatedCrdb(guid=GUID)]
