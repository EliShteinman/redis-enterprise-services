from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.cluster.cluster_target_resolver import SharedCredentialsTargetResolver
from redis_enterprise_services.cluster.crdb_task_waiter import CrdbTaskWaiter
from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.settings import load_settings
from redis_enterprise_services.crdbs.models import Crdb
from redis_enterprise_services.crdbs.repository import CrdbRepository
from redis_enterprise_services.exceptions.cluster import (
    CrdbTaskTimeoutError,
    UnrestorableFieldsError,
    UpdateOutcomeUnclearError,
)
from redis_enterprise_services.steps.crdb_task_tracker import CrdbTaskTracker
from redis_enterprise_services.steps.undo_task_id import undo_task_id
from redis_enterprise_services.steps.update_crdb_instances import (
    CrdbInstancesSnapshot,
    UpdateCrdbInstancesInput,
    UpdateCrdbInstancesStep,
)

NEW_PERMISSIONS: JsonValue = [{"role_uid": 3, "redis_acl_uid": 3}]
STEP_INPUT: UpdateCrdbInstancesInput = UpdateCrdbInstancesInput(
    coordinator=ClusterAddress(network="net-a", api_url="https://cluster-a:9443"),
    guid="g",
    values_by_instance={1: {"roles_permissions": NEW_PERMISSIONS}},
    task_id="t",
)
BEFORE: CrdbInstancesSnapshot = CrdbInstancesSnapshot(values_by_instance={1: {"roles_permissions": []}})


def crdb_holding(*, db_config: dict[str, JsonValue]) -> Crdb:
    return Crdb.model_validate(
        obj={
            "guid": "g",
            "name": "orders",
            "default_db_config": {},
            "instances": [{"id": 1, "cluster": {"url": "https://cluster-a:9443"}, "db_config": db_config}],
        }
    )


def step_reading(
    *, db_config: dict[str, JsonValue], task: JsonValue = None
) -> tuple[UpdateCrdbInstancesStep, MagicMock, MagicMock]:
    repository: MagicMock = create_autospec(spec=CrdbRepository, instance=True)
    repository.read.return_value = crdb_holding(db_config=db_config)
    task_waiter: MagicMock = create_autospec(spec=CrdbTaskWaiter, instance=True)
    task_waiter.read_task.return_value = task if task is not None else {"status": "finished"}
    step: UpdateCrdbInstancesStep = UpdateCrdbInstancesStep(
        repository=repository,
        task_tracker=CrdbTaskTracker(
            task_waiter=task_waiter, settings=load_settings().crdb.task, status_field="status"
        ),
        target_resolver=SharedCredentialsTargetResolver(
            credentials=ClusterCredentials(username="admin", password=SecretStr("secret"))
        ),
        list_fields=frozenset({"roles_permissions"}),
    )
    return step, repository, task_waiter


def ignore(result: CrdbInstancesSnapshot) -> None:
    return None


def test_an_instance_without_permissions_is_snapshotted_as_an_empty_list() -> None:
    step, _, _ = step_reading(db_config={})
    kept: list[CrdbInstancesSnapshot] = []

    step.execute(step_input=STEP_INPUT, keep_result=lambda result: kept.append(result))

    assert kept == [BEFORE]


@pytest.mark.parametrize(
    argnames=("db_config", "found"),
    argvalues=[
        pytest.param({"roles_permissions": NEW_PERMISSIONS}, BEFORE, id="applied"),
        pytest.param({}, None, id="not-applied"),
    ],
)
def test_the_outcome_is_found_by_what_the_instances_hold(
    db_config: dict[str, JsonValue], found: CrdbInstancesSnapshot | None
) -> None:
    step, _, _ = step_reading(db_config=db_config)

    assert (
        step.find_outcome(step_input=STEP_INPUT, kept_result=BEFORE, keep_result_if_none_kept=ignore) == found
    )


def test_instances_holding_something_else_need_manual_intervention() -> None:
    step, _, _ = step_reading(db_config={"roles_permissions": [{"role_uid": 9, "redis_acl_uid": 9}]})

    with pytest.raises(expected_exception=UpdateOutcomeUnclearError):
        step.find_outcome(step_input=STEP_INPUT, kept_result=BEFORE, keep_result_if_none_kept=ignore)


def test_undoing_puts_the_old_values_back_on_each_instance() -> None:
    step, repository, _ = step_reading(db_config={"roles_permissions": NEW_PERMISSIONS})

    step.compensate(step_input=STEP_INPUT, result=BEFORE)

    assert (
        repository.start_instances_update.call_args.kwargs["values_by_instance"] == BEFORE.values_by_instance
    )


def test_a_patch_whose_task_is_still_running_has_an_unknown_outcome() -> None:
    step, _, _ = step_reading(db_config={}, task={"status": "started"})

    with pytest.raises(expected_exception=CrdbTaskTimeoutError):
        step.find_outcome(step_input=STEP_INPUT, kept_result=BEFORE, keep_result_if_none_kept=ignore)


def test_undoing_first_waits_for_both_the_update_and_an_earlier_undo() -> None:
    step, _, task_waiter = step_reading(db_config={"roles_permissions": []}, task={"status": "started"})

    step.compensate(step_input=STEP_INPUT, result=BEFORE)

    assert [call.kwargs["task_id"] for call in task_waiter.wait_until_finished.call_args_list] == [
        "t",
        undo_task_id(task_id="t"),
    ]


def test_a_missing_field_that_is_not_a_list_is_refused_before_the_update() -> None:
    step, _, _ = step_reading(db_config={})
    unset_scalar: UpdateCrdbInstancesInput = STEP_INPUT.model_copy(
        update={"values_by_instance": {1: {"proxy_policy": "single"}}}
    )

    with pytest.raises(expected_exception=UnrestorableFieldsError):
        step.execute(step_input=unset_scalar, keep_result=ignore)
