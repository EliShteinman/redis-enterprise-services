from pathlib import Path
from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.cluster_target_resolver import ConfiguredCredentialsTargetResolver
from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.cluster.waiting.crdb_task_waiter import CrdbTaskWaiter
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.redis_api.crdb_settings import CrdbCreationSettings, CrdbTaskSettings
from redis_enterprise_services.config.settings import load_settings
from redis_enterprise_services.crdbs.repository import CrdbRepository
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.exceptions.cluster import (
    ClusterRejectedRequestError,
    CrdbTaskFailedError,
    CrdbTaskTimeoutError,
    UnreadableClusterResponseError,
)
from redis_enterprise_services.exceptions.saga import StepNeedsManualInterventionError
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
    settings=CrdbCreationSettings(causal_consistency=False, encryption=False, compression=3),
    task_id="16a0c036-6d3a-4ad0-9352-a56108ea8138",
)
NOT_FOUND: ClusterRejectedRequestError = ClusterRejectedRequestError(
    message="m", cluster_status_code=404, cluster_error_code="not_found"
)


class StepHarness:
    def __init__(self, *, task_settings: CrdbTaskSettings) -> None:
        self.repository: MagicMock = create_autospec(spec=CrdbRepository, instance=True)
        self.task_waiter: MagicMock = create_autospec(spec=CrdbTaskWaiter, instance=True)
        self.kept: list[CreatedCrdb] = []
        self.step: CreateCrdbStep = CreateCrdbStep(
            repository=self.repository,
            task_tracker=CrdbTaskTracker(
                task_waiter=self.task_waiter, settings=task_settings, status_field="status"
            ),
            target_resolver=ConfiguredCredentialsTargetResolver(
                credentials_by_api_url={
                    member.api_url: ClusterCredentials(username="admin", password=SecretStr("secret"))
                    for member in STEP_INPUT.members
                },
            ),
            guid_field="crdb_guid",
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


@pytest.fixture
def harness(config_dir: Path) -> StepHarness:
    return StepHarness(task_settings=load_settings(config_dir=config_dir).crdb.task)


def test_a_creation_is_started_with_the_settings_of_its_input(harness: StepHarness) -> None:
    harness.task_waiter.wait_until_finished.return_value = {"status": "finished", "crdb_guid": GUID}

    harness.step.execute(step_input=STEP_INPUT, keep_result=harness.keep)

    assert harness.repository.start_creation.call_args.kwargs["settings"] == STEP_INPUT.settings


def test_a_finished_creation_keeps_the_guid_of_its_task(harness: StepHarness) -> None:
    harness.task_waiter.wait_until_finished.return_value = {"status": "finished", "crdb_guid": GUID}

    harness.step.execute(step_input=STEP_INPUT, keep_result=harness.keep)

    assert harness.kept == [CreatedCrdb(guid=GUID)]


def test_a_creation_whose_task_never_arrived_left_nothing(harness: StepHarness) -> None:
    harness.repository.list_crdb_names.return_value = set()

    assert harness.find_outcome_with_task(task=NOT_FOUND) is None


def failed_task_harness(*, harness: StepHarness, crdb_names: set[str]) -> StepHarness:
    harness.repository.list_crdb_names.return_value = crdb_names
    harness.task_waiter.wait_until_finished.side_effect = CrdbTaskFailedError(
        message="failed", cluster_error_code=None
    )
    return harness


def test_a_creation_whose_task_failed_is_a_certain_failure(harness: StepHarness) -> None:
    with pytest.raises(expected_exception=CrdbTaskFailedError):
        failed_task_harness(harness=harness, crdb_names=set()).find_outcome_with_task(
            task={"status": "failed"}
        )


def test_a_failed_creation_that_left_a_crdb_of_its_name_needs_manual_intervention(
    harness: StepHarness,
) -> None:
    failed_task_harness(harness=harness, crdb_names={"orders"})

    with pytest.raises(expected_exception=StepNeedsManualInterventionError):
        harness.step.execute(step_input=STEP_INPUT, keep_result=harness.keep)


def test_a_creation_whose_task_finished_is_found_by_our_task_id(harness: StepHarness) -> None:
    found: CreatedCrdb | None = harness.find_outcome_with_task(task={"status": "finished", "crdb_guid": GUID})

    assert found == CreatedCrdb(guid=GUID)


def test_a_creation_whose_task_is_still_running_is_waited_for(harness: StepHarness) -> None:
    harness.task_waiter.wait_until_finished.return_value = {"status": "finished", "crdb_guid": GUID}

    assert harness.find_outcome_with_task(task={"status": "started"}) == CreatedCrdb(guid=GUID)


def test_a_creation_whose_task_outlives_the_wait_is_not_cancelled_but_left_unknown(
    harness: StepHarness,
) -> None:
    harness.task_waiter.wait_until_finished.side_effect = CrdbTaskTimeoutError(message="still started")

    with pytest.raises(expected_exception=CrdbTaskTimeoutError):
        harness.find_outcome_with_task(task={"status": "started"})


def test_deleting_a_crdb_that_is_already_gone_is_done(harness: StepHarness) -> None:
    harness.repository.start_deletion.side_effect = NOT_FOUND

    harness.step.compensate(step_input=STEP_INPUT, result=CreatedCrdb(guid=GUID))

    harness.task_waiter.wait_until_finished.assert_not_called()


def test_a_creation_sent_again_joins_the_task_that_already_reached_the_cluster(harness: StepHarness) -> None:
    harness.repository.start_creation.side_effect = ClusterRejectedRequestError(
        message="m", cluster_status_code=406, cluster_error_code="job_exists"
    )
    harness.task_waiter.wait_until_finished.return_value = {"status": "finished", "crdb_guid": GUID}

    harness.step.execute(step_input=STEP_INPUT, keep_result=harness.keep)

    assert harness.kept == [CreatedCrdb(guid=GUID)]


def test_a_task_without_a_status_is_an_unreadable_answer(harness: StepHarness) -> None:
    with pytest.raises(expected_exception=UnreadableClusterResponseError):
        harness.find_outcome_with_task(task={"crdb_guid": GUID})


def test_an_unknown_task_with_a_crdb_of_that_name_needs_manual_intervention(harness: StepHarness) -> None:
    harness.repository.list_crdb_names.return_value = {"orders"}

    with pytest.raises(expected_exception=StepNeedsManualInterventionError):
        harness.find_outcome_with_task(task=NOT_FOUND)
