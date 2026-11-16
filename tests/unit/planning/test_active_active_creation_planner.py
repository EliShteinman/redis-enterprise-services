from pydantic import BaseModel, JsonValue, SecretStr

from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.config.cluster_api_settings import ClusterFieldSettings
from redis_enterprise_services.config.cluster_credentials_settings import ClusterCredentialsSettings
from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.crdb_settings import CrdbCreationSettings
from redis_enterprise_services.config.database_defaults_settings import (
    ActiveActiveDefaults,
    DatabaseDefaultsSettings,
    DatabaseKindDefaults,
)
from redis_enterprise_services.config.user_resources_settings import UserResourcesSettings
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.planning.active_active_creation_planner import ActiveActiveCreationPlanner
from redis_enterprise_services.planning.active_active_spec import ActiveActiveSpec
from redis_enterprise_services.planning.crdb_spec import CrdbSpec
from redis_enterprise_services.planning.database_defaults import DatabaseDefaults
from redis_enterprise_services.planning.database_spec import DatabaseUserSpec
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming
from redis_enterprise_services.resources.models import CreatedResource
from redis_enterprise_services.saga.contract.keep_result import KeepResult
from redis_enterprise_services.saga.contract.step_kind import StepKind
from redis_enterprise_services.saga.plan.saga_plan import SagaPlan
from redis_enterprise_services.saga.plan.step_results import StepResults
from redis_enterprise_services.steps.create_crdb import CreatedCrdb
from redis_enterprise_services.steps.find_local_crdb_instance import LocalCrdbInstance

NY: str = "redis.ny.example.com"
TLV: str = "redis.tlv.example.com"
ADMIN: ClusterCredentialsSettings = ClusterCredentialsSettings(username="admin", password=SecretStr("secret"))
DEFAULT_USER_PASSWORD: SecretStr = SecretStr("default-user-secret")


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


class BodyWithSecret:
    def creation_body(self, *, spec: NewDatabase, cluster: ClusterAddress) -> dict[str, JsonValue]:
        return {"name": spec.name, "memory_size": spec.memory_size, "authentication_redis_pass": "secret"}


USER_RESOURCES: UserResourcesSettings = UserResourcesSettings(
    acl_name_template="{database}-{user}-acl",
    role_name_template="{database}-{user}-role",
    role_management="db_viewer",
)
PLANNER: ActiveActiveCreationPlanner = ActiveActiveCreationPlanner(
    role_management=USER_RESOURCES.role_management,
    cluster_fields=ClusterFieldSettings(
        status="status",
        error_code="error_code",
        action_uid="action_uid",
        roles_permissions="roles_permissions",
        name="name",
        memory_size="memory_size",
    ),
    resource_naming=UserResourceNaming(settings=USER_RESOURCES),
    database_body_builder=BodyWithSecret(),
    secret_fields=frozenset({"authentication_redis_pass"}),
    database_defaults=DatabaseDefaults(
        settings=DatabaseDefaultsSettings(
            single_site=DatabaseKindDefaults(database={}, persistence_values={}),
            active_active=ActiveActiveDefaults(
                database={},
                persistence_values={},
                crdb=CrdbCreationSettings(causal_consistency=False, encryption=False, compression=3),
            ),
        )
    ),
    create_crdb_step=IdleStep(),
    find_local_instance_step=IdleStep(),
    create_acl_step=IdleStep(),
    create_role_step=IdleStep(),
    create_user_step=IdleStep(),
    update_instances_step=IdleStep(),
    read_database_step=IdleStep(),
    read_crdb_step=IdleStep(),
)
CLUSTERS: list[ConfiguredCluster] = [
    ConfiguredCluster(
        fqdn=NY,
        network="net-a",
        environment="DEV",
        site="ny",
        type="generic",
        api_url=f"https://{NY}:9443",
        credentials=ADMIN,
        default_user_password=DEFAULT_USER_PASSWORD,
        crdb_overrides={"compression": 6},
    ),
    ConfiguredCluster(
        fqdn=TLV,
        network="net-a",
        environment="DEV",
        site="tlv",
        type="generic",
        api_url=f"https://{TLV}:9443",
        credentials=ADMIN,
        default_user_password=DEFAULT_USER_PASSWORD,
        crdb_overrides={"compression": 1},
    ),
]
SPEC: ActiveActiveSpec = ActiveActiveSpec(
    database=NewDatabase(name="orders", memory_size=104857600),
    users=[DatabaseUserSpec(name="app", password="p1-passw0rd", acl_rule="+@all ~orders:*")],
)


def plan(*, spec: ActiveActiveSpec = SPEC) -> SagaPlan:
    return PLANNER.plan(saga_id="trace-1", clusters=CLUSTERS, spec=spec)


def step_inputs_by_key(*, spec: ActiveActiveSpec = SPEC) -> dict[str, JsonValue]:
    results: StepResults = StepResults()
    results.keep(key="crdb", result=CreatedCrdb(guid="g"))
    results.keep(key=f"{NY}/local-database", result=LocalCrdbInstance(instance_id=1, db_uid=7))
    results.keep(key=f"{TLV}/local-database", result=LocalCrdbInstance(instance_id=2, db_uid=4))
    for key, uid in {
        f"{NY}/acl/app": 11,
        f"{NY}/role/app": 12,
        f"{TLV}/acl/app": 21,
        f"{TLV}/role/app": 22,
    }.items():
        results.keep(key=key, result=CreatedResource(uid=uid, name=key, action_uid=None, fields={}))
    return {step.key: step.prepare(step_results=results).step_input for step in plan(spec=spec).steps}


def test_the_crdb_comes_first_then_each_site_then_one_permissions_patch_then_the_reads() -> None:
    assert [step.key for step in plan().steps] == [
        "crdb",
        f"{NY}/local-database",
        f"{TLV}/local-database",
        f"{NY}/acl/app",
        f"{NY}/role/app",
        f"{NY}/user/app",
        f"{TLV}/acl/app",
        f"{TLV}/role/app",
        f"{TLV}/user/app",
        "permissions",
        f"{NY}/read-database",
        f"{TLV}/read-database",
        "read-crdb",
    ]


def test_each_role_is_limited_to_the_local_database_of_its_site() -> None:
    inputs: dict[str, JsonValue] = step_inputs_by_key()

    assert [inputs[f"{site}/role/app"]["spec"]["database_uids"] for site in (NY, TLV)] == [[7], [4]]  # type: ignore[index]


def test_the_permissions_patch_pairs_each_instance_with_its_own_role_and_acl() -> None:
    assert step_inputs_by_key()["permissions"]["values_by_instance"] == {  # type: ignore[index]
        "1": {"roles_permissions": [{"role_uid": 12, "redis_acl_uid": 11}]},
        "2": {"roles_permissions": [{"role_uid": 22, "redis_acl_uid": 21}]},
    }


def test_the_crdb_check_expects_what_is_sent_without_secrets() -> None:
    assert step_inputs_by_key()["read-crdb"]["expected_config"] == {  # type: ignore[index]
        "name": "orders",
        "memory_size": 104857600,
    }


def test_the_crdb_check_expects_the_sync_settings_that_are_sent() -> None:
    assert step_inputs_by_key()["read-crdb"]["expected_settings"] == {  # type: ignore[index]
        "causal_consistency": False,
        "encryption": False,
        "compression": 6,
    }


def test_the_crdb_is_created_with_the_crdb_settings_of_the_coordinator() -> None:
    assert step_inputs_by_key()["crdb"]["settings"] == {  # type: ignore[index]
        "causal_consistency": False,
        "encryption": False,
        "compression": 6,
    }


SPEC_WITH_CRDB: ActiveActiveSpec = SPEC.model_copy(
    update={"crdb": CrdbSpec(causal_consistency=True, compression=2)}
)
REQUESTED_OVER_CONFIGURED: dict[str, JsonValue] = {
    "causal_consistency": True,
    "encryption": False,
    "compression": 2,
}


def test_the_crdb_is_created_with_the_crdb_settings_of_the_request() -> None:
    assert step_inputs_by_key(spec=SPEC_WITH_CRDB)["crdb"]["settings"] == REQUESTED_OVER_CONFIGURED  # type: ignore[index]


def test_the_crdb_check_expects_the_crdb_settings_of_the_request() -> None:
    assert (
        step_inputs_by_key(spec=SPEC_WITH_CRDB)["read-crdb"]["expected_settings"]  # type: ignore[index]
        == REQUESTED_OVER_CONFIGURED
    )


def test_the_plan_locks_the_database_and_users_on_every_site() -> None:
    assert plan().lock_keys == [
        f"https://{NY}:9443/database/orders",
        f"https://{NY}:9443/user/app",
        f"https://{TLV}:9443/database/orders",
        f"https://{TLV}:9443/user/app",
    ]
