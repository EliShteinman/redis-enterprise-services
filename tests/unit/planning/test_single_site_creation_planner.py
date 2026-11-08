import pytest
from pydantic import BaseModel, JsonValue, ValidationError

from redis_enterprise_services.config.cluster_api_settings import ClusterFieldSettings
from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.user_resources_settings import UserResourcesSettings
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.planning.database_creation_request import (
    DatabaseCreationRequest,
    DatabaseUserRequest,
)
from redis_enterprise_services.planning.single_site_creation_planner import SingleSiteCreationPlanner
from redis_enterprise_services.planning.user_resource_names import UserResourceNames
from redis_enterprise_services.resources.models import CreatedResource
from redis_enterprise_services.saga.contract.keep_result import KeepResult
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.saga.plan.saga_plan import SagaPlan
from redis_enterprise_services.saga.plan.step_results import StepResults


class IdleStep[TInput: BaseModel, TResult: BaseModel]:
    @property
    def kind(self) -> StepKind:
        return StepKind.COMPENSATABLE

    def execute(self, *, step_input: TInput, keep_result: KeepResult[TResult]) -> None:
        pass

    def find_outcome(
        self, *, step_input: TInput, kept_result: TResult | None, keep_found_result: KeepResult[TResult]
    ) -> TResult | None:
        return kept_result

    def compensate(self, *, step_input: TInput, result: TResult) -> None:
        pass


USER_RESOURCES: UserResourcesSettings = UserResourcesSettings(
    acl_name_template="{database}-{user}-acl",
    role_name_template="{database}-{user}-role",
    role_management="db_viewer",
)
PLANNER: SingleSiteCreationPlanner = SingleSiteCreationPlanner(
    user_resources=USER_RESOURCES,
    cluster_fields=ClusterFieldSettings(
        status="status",
        error_code="error_code",
        action_uid="action_uid",
        roles_permissions="roles_permissions",
    ),
    resource_names=UserResourceNames(settings=USER_RESOURCES),
    create_database=IdleStep(),
    create_acl=IdleStep(),
    create_role=IdleStep(),
    create_user=IdleStep(),
    update_database=IdleStep(),
)
CLUSTER: ConfiguredCluster = ConfiguredCluster(
    name="c1", network="net-a", environment="DEV", site="dc1", type="generic", api_url="https://c1:9443"
)
DATABASE: NewDatabase = NewDatabase(name="orders", memory_size=104857600)
USERS: list[DatabaseUserRequest] = [
    DatabaseUserRequest(name="app", password="p1", acl_rule="+@all ~orders:*"),
    DatabaseUserRequest(name="report", password="p2", acl_rule="+@read ~orders:*"),
]
UIDS: dict[str, int] = {"database": 7, "acl/app": 11, "role/app": 12, "acl/report": 21, "role/report": 22}


def plan(*, users: list[DatabaseUserRequest]) -> SagaPlan:
    return PLANNER.plan(cluster=CLUSTER, database=DATABASE, users=users)


def inputs_after_earlier_steps() -> dict[str, JsonValue]:
    step_results: StepResults = StepResults()
    for key, uid in UIDS.items():
        step_results.keep(key=key, result=CreatedResource(uid=uid, name=key, action_uid=None))
    return {step.key: step.prepare(step_results=step_results).step_input for step in plan(users=USERS).steps}


def test_the_database_comes_first_then_each_user_then_one_permissions_update() -> None:
    assert [step.key for step in plan(users=USERS).steps] == [
        "database",
        "acl/app",
        "role/app",
        "user/app",
        "acl/report",
        "role/report",
        "user/report",
        "permissions",
    ]


def test_a_database_without_users_is_one_step() -> None:
    assert [step.key for step in plan(users=[]).steps] == ["database"]


def test_the_plan_locks_the_database_and_user_names_on_its_cluster() -> None:
    assert plan(users=USERS).lock_keys == ["c1/orders", "c1/user/app", "c1/user/report"]


def test_each_acl_is_named_from_the_config_and_carries_the_requested_rules() -> None:
    assert inputs_after_earlier_steps()["acl/report"] == {
        "cluster": {"network": "net-a", "api_url": "https://c1:9443"},
        "spec": {"name": "orders-report-acl", "acl": "+@read ~orders:*"},
    }


def test_each_role_is_limited_to_the_new_database() -> None:
    assert inputs_after_earlier_steps()["role/report"] == {
        "cluster": {"network": "net-a", "api_url": "https://c1:9443"},
        "spec": {"name": "orders-report-role", "management": "db_viewer", "database_uids": [7]},
    }


def test_each_user_gets_its_own_role() -> None:
    assert inputs_after_earlier_steps()["user/report"] == {
        "cluster": {"network": "net-a", "api_url": "https://c1:9443"},
        "spec": {"name": "report", "password": "p2", "role_uids": [22]},
    }


def test_the_permissions_pair_each_role_with_its_own_acl() -> None:
    assert inputs_after_earlier_steps()["permissions"] == {
        "cluster": {"network": "net-a", "api_url": "https://c1:9443"},
        "uid": 7,
        "values": {
            "roles_permissions": [
                {"role_uid": 12, "redis_acl_uid": 11},
                {"role_uid": 22, "redis_acl_uid": 21},
            ]
        },
    }


def test_a_user_requested_twice_is_refused() -> None:
    with pytest.raises(expected_exception=ValidationError):
        DatabaseCreationRequest(database=DATABASE, users=[USERS[0], USERS[0]])


@pytest.mark.parametrize(
    argnames="template",
    argvalues=[
        pytest.param("{db}-{user}-acl", id="unknown placeholder"),
        pytest.param("{database}-acl", id="same name for every user"),
        pytest.param("{database}_{user}-acl", id="placeholders not joined by the separator"),
    ],
)
def test_a_name_template_that_does_not_name_each_user_is_refused(template: str) -> None:
    with pytest.raises(expected_exception=ValidationError):
        UserResourcesSettings(
            acl_name_template=template,
            role_name_template="{database}-{user}-role",
            role_management="db_viewer",
        )
