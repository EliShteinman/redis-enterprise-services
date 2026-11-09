import pytest
from pydantic import BaseModel, JsonValue

from redis_enterprise_services.config.cluster_api_settings import ClusterFieldSettings
from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.user_resources_settings import UserResourcesSettings
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.planning.database_spec import (
    DatabaseSpec,
    DatabaseUserSpec,
)
from redis_enterprise_services.planning.planned_resources import planned_resources_by_step_key
from redis_enterprise_services.planning.single_site_creation_planner import SingleSiteCreationPlanner
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming
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
        self,
        *,
        step_input: TInput,
        kept_result: TResult | None,
        keep_result_if_none_kept: KeepResult[TResult],
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
    role_management=USER_RESOURCES.role_management,
    cluster_fields=ClusterFieldSettings(
        status="status",
        error_code="error_code",
        action_uid="action_uid",
        roles_permissions="roles_permissions",
    ),
    resource_naming=UserResourceNaming(settings=USER_RESOURCES),
    create_database_step=IdleStep(),
    create_acl_step=IdleStep(),
    create_role_step=IdleStep(),
    create_user_step=IdleStep(),
    update_database_step=IdleStep(),
)
CLUSTER: ConfiguredCluster = ConfiguredCluster(
    name="c1", network="net-a", environment="DEV", site="dc1", type="generic", api_url="https://c1:9443"
)
DATABASE: NewDatabase = NewDatabase(name="orders", memory_size=104857600)
USERS: list[DatabaseUserSpec] = [
    DatabaseUserSpec(name="app", password="p1", acl_rule="+@all ~orders:*"),
    DatabaseUserSpec(name="report", password="p2", acl_rule="+@read ~orders:*"),
]
CREATED_UIDS_BY_STEP_KEY: dict[str, int] = {
    "database": 7,
    "acl/app": 11,
    "role/app": 12,
    "acl/report": 21,
    "role/report": 22,
}


def plan(*, users: list[DatabaseUserSpec]) -> SagaPlan:
    return PLANNER.plan(cluster=CLUSTER, spec=DatabaseSpec(database=DATABASE, users=users))


def step_inputs_by_key() -> dict[str, JsonValue]:
    step_results: StepResults = StepResults()
    for key, uid in CREATED_UIDS_BY_STEP_KEY.items():
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


def test_the_plan_locks_the_database_and_user_names_on_its_cluster_address() -> None:
    assert plan(users=USERS).lock_keys == [
        "https://c1:9443/database/orders",
        "https://c1:9443/user/app",
        "https://c1:9443/user/report",
    ]


def test_each_acl_is_named_from_the_config_and_carries_the_requested_rules() -> None:
    assert step_inputs_by_key()["acl/report"] == {
        "cluster": {"network": "net-a", "api_url": "https://c1:9443"},
        "spec": {"name": "orders-report-acl", "acl": "+@read ~orders:*"},
    }


def test_each_role_is_limited_to_the_new_database() -> None:
    assert step_inputs_by_key()["role/report"] == {
        "cluster": {"network": "net-a", "api_url": "https://c1:9443"},
        "spec": {"name": "orders-report-role", "management": "db_viewer", "database_uids": [7]},
    }


def test_each_user_gets_its_own_role() -> None:
    assert step_inputs_by_key()["user/report"] == {
        "cluster": {"network": "net-a", "api_url": "https://c1:9443"},
        "spec": {"name": "report", "password": "p2", "role_uids": [22]},
    }


def test_the_permissions_pair_each_role_with_its_own_acl() -> None:
    assert step_inputs_by_key()["permissions"] == {
        "cluster": {"network": "net-a", "api_url": "https://c1:9443"},
        "uid": 7,
        "values": {
            "roles_permissions": [
                {"role_uid": 12, "redis_acl_uid": 11},
                {"role_uid": 22, "redis_acl_uid": 21},
            ]
        },
    }


@pytest.mark.parametrize(argnames="users", argvalues=[[], USERS])
def test_the_planned_resources_name_exactly_the_planned_steps(users: list[DatabaseUserSpec]) -> None:
    assert set(
        planned_resources_by_step_key(
            spec=DatabaseSpec(database=DATABASE, users=users),
            resource_naming=UserResourceNaming(settings=USER_RESOURCES),
        )
    ) == {step.key for step in plan(users=users).steps}
