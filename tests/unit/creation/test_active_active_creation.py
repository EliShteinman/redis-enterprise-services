from pathlib import Path
from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import JsonValue, SecretStr

from redis_enterprise_services.config.clusters.cluster_credentials_settings import ClusterCredentialsSettings
from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.defaults.user_resources_settings import UserResourcesSettings
from redis_enterprise_services.config.redis_api.crdb_settings import CrdbCreationSettings
from redis_enterprise_services.config.service.operation_settings import OperationSettings
from redis_enterprise_services.config.settings import Settings, load_settings
from redis_enterprise_services.creation.active_active_preparation import ActiveActivePreparation
from redis_enterprise_services.creation.active_active_record_reader import ActiveActiveRecordReader
from redis_enterprise_services.creation.create_crdb_request import CreateCrdbRequest
from redis_enterprise_services.creation.creation_outcome_translator import CreationOutcomeTranslator
from redis_enterprise_services.creation.prepared_active_active_creation import PreparedActiveActiveCreation
from redis_enterprise_services.databases.new_database import NewDatabase, SnapshotRule
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.exceptions.planning import DuplicateSitesError, MixedNetworksError
from redis_enterprise_services.operations.errors.public_error import PublicError
from redis_enterprise_services.operations.errors.public_errors import PublicErrors
from redis_enterprise_services.operations.operation import Operation
from redis_enterprise_services.operations.remaining_resource import RemainingResource
from redis_enterprise_services.operations.results.active_active_database_result import (
    ActiveActiveDatabaseResult,
)
from redis_enterprise_services.planning.naming.name_validator import NameValidator
from redis_enterprise_services.planning.naming.user_names_validator import UserNamesValidator
from redis_enterprise_services.planning.placement.site_cluster_resolver import SiteClusterResolver
from redis_enterprise_services.planning.planned.user_resource_naming import UserResourceNaming
from redis_enterprise_services.planning.spec.active_active_spec import ActiveActiveSpec
from redis_enterprise_services.planning.spec.database_defaults import DatabaseDefaults
from redis_enterprise_services.planning.spec.database_spec import DatabaseUserSpec
from redis_enterprise_services.saga.contract.saga_record import (
    SagaRecord,
    SagaStatus,
    StepError,
    StepRecord,
    StepStatus,
)
from redis_enterprise_services.saga.contract.step_kind import StepKind

NY_FQDN: str = "redis.ny.example.com"
TLV_FQDN: str = "redis.tlv.example.com"
NY_URL: str = f"https://{NY_FQDN}:9443"
TLV_URL: str = f"https://{TLV_FQDN}:9443"
ADMIN: ClusterCredentialsSettings = ClusterCredentialsSettings(username="admin", password=SecretStr("secret"))
DEFAULT_USER_PASSWORD: SecretStr = SecretStr("default-user-secret")
ANOTHER_DEFAULT_USER_PASSWORD: SecretStr = SecretStr("another-default-user-secret")

NY: ConfiguredCluster = ConfiguredCluster(
    fqdn=NY_FQDN,
    network="net-a",
    environment="DEV",
    site="NY",
    type="generic",
    api_url=NY_URL,
    credentials=ADMIN,
    default_user_password=DEFAULT_USER_PASSWORD,
)
TLV: ConfiguredCluster = NY.model_copy(update={"fqdn": TLV_FQDN, "site": "TLV", "api_url": TLV_URL})
TLV_ON_ANOTHER_NETWORK: ConfiguredCluster = TLV.model_copy(update={"network": "net-b"})
GUID: str = "d71cefce-4e31-41fd-b654-37cbb2f39a01"
DATABASE: NewDatabase = NewDatabase(name="orders", memory_size=104857600)
APP_USER: DatabaseUserSpec = DatabaseUserSpec(name="app", password="p1-passw0rd", acl_rule="+@all ~orders:*")
CRDB_SETTINGS: CrdbCreationSettings = CrdbCreationSettings(
    causal_consistency=False, encryption=False, compression=3
)
REQUEST: CreateCrdbRequest = CreateCrdbRequest.model_validate(
    obj={
        "target": {
            "sites": [
                {"environment": "DEV", "network": "net-a", "site": "NY", "cluster": "generic"},
                {"environment": "DEV", "network": "net-a", "site": "TLV", "cluster": "generic"},
            ]
        },
        "spec": {"database": {"name": "orders", "memory_size": 104857600}},
    }
)
WITHOUT_USERS: PreparedActiveActiveCreation = PreparedActiveActiveCreation(
    clusters=[NY, TLV], spec=ActiveActiveSpec(database=DATABASE, users=[])
)
WITH_A_USER: PreparedActiveActiveCreation = PreparedActiveActiveCreation(
    clusters=[NY, TLV], spec=ActiveActiveSpec(database=DATABASE, users=[APP_USER])
)
INTERRUPTION_ERROR: PublicError = PublicError(
    code="internal_error", kind="needs_investigation", message="interrupted"
)


def preparation(
    *,
    clusters: list[ConfiguredCluster],
    filled: list[NewDatabase],
    crdb_settings: list[CrdbCreationSettings] | None = None,
) -> ActiveActivePreparation:
    resolver: MagicMock = create_autospec(spec=SiteClusterResolver, instance=True)
    resolver.resolve.side_effect = clusters
    defaults: MagicMock = create_autospec(spec=DatabaseDefaults, instance=True)
    defaults.fill_in.side_effect = filled
    defaults.crdb_settings.side_effect = crdb_settings or [CRDB_SETTINGS, CRDB_SETTINGS]
    return ActiveActivePreparation(
        name_validator=create_autospec(spec=NameValidator, instance=True),
        user_names_validator=create_autospec(spec=UserNamesValidator, instance=True),
        site_cluster_resolver=resolver,
        database_defaults=defaults,
    )


def test_an_active_active_creation_is_prepared_on_every_site_in_request_order() -> None:
    prepared: PreparedActiveActiveCreation = preparation(
        clusters=[NY, TLV], filled=[DATABASE, DATABASE]
    ).prepare(creation_request=REQUEST)

    assert [cluster.fqdn for cluster in prepared.clusters] == [NY_FQDN, TLV_FQDN]


def test_sites_on_more_than_one_network_are_refused() -> None:
    with pytest.raises(expected_exception=MixedNetworksError):
        preparation(clusters=[NY, TLV_ON_ANOTHER_NETWORK], filled=[DATABASE, DATABASE]).prepare(
            creation_request=REQUEST
        )


def test_two_sites_on_the_same_cluster_are_refused() -> None:
    with pytest.raises(expected_exception=DuplicateSitesError):
        preparation(clusters=[NY, NY], filled=[DATABASE, DATABASE]).prepare(creation_request=REQUEST)


@pytest.mark.parametrize(
    argnames="second",
    argvalues=[
        pytest.param(TLV.model_copy(update={"fqdn": NY_FQDN}), id="same-fqdn"),
        pytest.param(TLV.model_copy(update={"api_url": f"https://{NY_FQDN}:9444"}), id="same-host"),
    ],
)
def test_different_clusters_that_share_an_fqdn_or_host_are_a_configuration_error(
    second: ConfiguredCluster,
) -> None:
    with pytest.raises(expected_exception=ConfigurationError):
        preparation(clusters=[NY, second], filled=[DATABASE, DATABASE]).prepare(creation_request=REQUEST)


def test_database_defaults_that_differ_between_sites_are_a_configuration_error() -> None:
    other: NewDatabase = DATABASE.model_copy(update={"replication": True})

    with pytest.raises(expected_exception=ConfigurationError):
        preparation(clusters=[NY, TLV], filled=[DATABASE, other]).prepare(creation_request=REQUEST)


def test_a_persistence_mode_that_differs_between_sites_names_only_the_mode() -> None:
    snapshot: NewDatabase = DATABASE.model_copy(
        update={"data_persistence": "snapshot", "snapshot_policy": [SnapshotRule(secs=3600, writes=1)]}
    )
    aof: NewDatabase = DATABASE.model_copy(
        update={"data_persistence": "aof", "aof_policy": "appendfsync-every-sec"}
    )

    with pytest.raises(expected_exception=ConfigurationError) as refusal:
        preparation(clusters=[NY, TLV], filled=[aof, snapshot]).prepare(creation_request=REQUEST)

    assert "['data_persistence']" in refusal.value.message


def test_crdb_settings_that_differ_between_sites_are_a_configuration_error() -> None:
    encrypted: CrdbCreationSettings = CRDB_SETTINGS.model_copy(update={"encryption": True})

    with pytest.raises(expected_exception=ConfigurationError) as refusal:
        preparation(
            clusters=[NY, TLV], filled=[DATABASE, DATABASE], crdb_settings=[CRDB_SETTINGS, encrypted]
        ).prepare(creation_request=REQUEST)

    assert "['encryption']" in refusal.value.message


def refusal_of_different_default_user_passwords() -> ConfigurationError:
    second: ConfiguredCluster = TLV.model_copy(
        update={"default_user_password": ANOTHER_DEFAULT_USER_PASSWORD}
    )
    with pytest.raises(expected_exception=ConfigurationError) as refusal:
        preparation(clusters=[NY, second], filled=[DATABASE, DATABASE]).prepare(creation_request=REQUEST)
    return refusal.value


def test_clusters_with_different_default_user_passwords_are_a_configuration_error() -> None:
    assert refusal_of_different_default_user_passwords().code == "configuration_error"


def test_the_refusal_of_different_default_user_passwords_shows_no_password() -> None:
    message: str = refusal_of_different_default_user_passwords().message

    assert "default-user-secret" not in message


@pytest.fixture
def translator(config_dir: Path) -> CreationOutcomeTranslator[PreparedActiveActiveCreation]:
    settings: Settings = load_settings(config_dir=config_dir)
    return CreationOutcomeTranslator(
        record_reader=ActiveActiveRecordReader(
            resource_naming=UserResourceNaming(
                settings=UserResourcesSettings(
                    acl_name_template="{database}-{user}-acl",
                    role_name_template="{database}-{user}-role",
                    role_management="db_viewer",
                )
            ),
            database_settings=settings.database,
            cluster_fields=settings.cluster_api.fields,
        ),
        public_errors=PublicErrors(
            settings=OperationSettings(
                public_code_by_internal_code={
                    "cluster_rejected_request": "cluster_request_failed",
                    "database_activation_timeout": "cluster_timeout",
                },
                public_codes_with_cluster_details=frozenset({"cluster_request_failed", "cluster_timeout"}),
                error_kind_by_code={},
            ),
            internal_error_message="internal error",
            unexpected_error_message="internal error: unexpected {error_type}",
        ),
    )


def done_step(*, key: str, result: JsonValue) -> StepRecord:
    return StepRecord(key=key, kind=StepKind.COMPENSATABLE, status=StepStatus.DONE, result=result)


def created_resource(*, uid: int, name: str, fields: dict[str, JsonValue] | None = None) -> JsonValue:
    return {"uid": uid, "name": name, "action_uid": None, "fields": fields or {}}


def remaining_after_manual_intervention(
    *, translator: CreationOutcomeTranslator[PreparedActiveActiveCreation]
) -> list[RemainingResource]:
    record: SagaRecord = SagaRecord(
        saga_id="trace-1",
        status=SagaStatus.REQUIRES_MANUAL_INTERVENTION,
        steps=[
            done_step(key="crdb", result={"guid": GUID}),
            StepRecord(
                key=f"{TLV_FQDN}/acl/app",
                kind=StepKind.COMPENSATABLE,
                status=StepStatus.COMPENSATION_FAILED,
                result=created_resource(uid=21, name="orders-app-acl"),
            ),
        ],
        stopped_at=f"{TLV_FQDN}/acl/app",
    )
    return translator.remaining_resources(prepared_creation=WITH_A_USER, record=record)


def test_a_crdb_left_behind_is_reported_on_the_coordinator_with_its_guid(
    translator: CreationOutcomeTranslator[PreparedActiveActiveCreation],
) -> None:
    crdb: RemainingResource = remaining_after_manual_intervention(translator=translator)[0]

    assert (crdb.resource_type, crdb.cluster_url, str(crdb.crdb_guid)) == ("crdb", NY_URL, GUID)


def test_a_user_resource_left_behind_is_reported_on_its_own_site(
    translator: CreationOutcomeTranslator[PreparedActiveActiveCreation],
) -> None:
    acl: RemainingResource = remaining_after_manual_intervention(translator=translator)[1]

    assert (acl.resource_type, acl.cluster_url, acl.uid) == ("acl", TLV_URL, 21)


def test_active_active_permissions_left_behind_are_named_by_the_crdb_guid(
    translator: CreationOutcomeTranslator[PreparedActiveActiveCreation],
) -> None:
    record: SagaRecord = SagaRecord(
        saga_id="trace-1",
        status=SagaStatus.REQUIRES_MANUAL_INTERVENTION,
        steps=[
            done_step(key="crdb", result={"guid": GUID}),
            StepRecord(key="permissions", kind=StepKind.COMPENSATABLE, status=StepStatus.COMPENSATION_FAILED),
        ],
    )

    remaining: list[RemainingResource] = translator.remaining_resources(
        prepared_creation=WITH_A_USER, record=record
    )

    assert [(item.resource_type, str(item.crdb_guid), item.uid) for item in remaining] == [
        ("crdb", GUID, None),
        ("permissions", GUID, None),
    ]


@pytest.mark.parametrize(
    argnames=("prepared_creation", "stopped_at", "error"),
    argvalues=[
        pytest.param(
            WITH_A_USER,
            f"{TLV_FQDN}/acl/app",
            StepError(code="cluster_rejected_request", message="refused", remote_code="invalid_param"),
            id="user-resource",
        ),
        pytest.param(
            WITHOUT_USERS,
            f"{TLV_FQDN}/local-database",
            StepError(code="database_activation_timeout", message="slow"),
            id="local-database",
        ),
    ],
)
def test_the_error_names_the_site_of_the_step_that_stopped(
    translator: CreationOutcomeTranslator[PreparedActiveActiveCreation],
    prepared_creation: PreparedActiveActiveCreation,
    stopped_at: str,
    error: StepError,
) -> None:
    record: SagaRecord = SagaRecord(
        saga_id="trace-1",
        status=SagaStatus.ROLLED_BACK,
        steps=[
            StepRecord(key=stopped_at, kind=StepKind.COMPENSATABLE, status=StepStatus.FAILED, error=error)
        ],
        stopped_at=stopped_at,
    )

    operation: Operation = translator.operation_from_ended_record(
        trace_id="trace-1",
        prepared_creation=prepared_creation,
        record=record,
        interruption_error=INTERRUPTION_ERROR,
    )

    assert operation.error is not None and operation.error.cluster_url == TLV_URL


def read_back(*, uid: int, fqdn: str) -> JsonValue:
    return {
        "values": {
            **DATABASE.model_dump(mode="json"),
            "uid": uid,
            "endpoints": [{"dns_name": f"redis-12000.{fqdn}", "port": 12000, "addr": ["10.0.0.1"]}],
        },
        "cluster_state_id": 1,
    }


def user_steps_on(*, fqdn: str, first_uid: int) -> list[StepRecord]:
    return [
        done_step(
            key=f"{fqdn}/acl/app",
            result=created_resource(
                uid=first_uid,
                name="orders-app-acl",
                fields={"name": "orders-app-acl", "acl": APP_USER.acl_rule},
            ),
        ),
        done_step(key=f"{fqdn}/role/app", result=created_resource(uid=first_uid + 1, name="orders-app-role")),
        done_step(key=f"{fqdn}/user/app", result=created_resource(uid=first_uid + 2, name="app")),
    ]


def created(
    *, translator: CreationOutcomeTranslator[PreparedActiveActiveCreation]
) -> ActiveActiveDatabaseResult:
    record: SagaRecord = SagaRecord(
        saga_id="trace-1",
        status=SagaStatus.SUCCEEDED,
        steps=[
            done_step(key="crdb", result={"guid": GUID}),
            *user_steps_on(fqdn=NY_FQDN, first_uid=10),
            *user_steps_on(fqdn=TLV_FQDN, first_uid=20),
            done_step(key=f"{NY_FQDN}/read-database", result=read_back(uid=7, fqdn=NY_FQDN)),
            done_step(key=f"{TLV_FQDN}/read-database", result=read_back(uid=4, fqdn=TLV_FQDN)),
            done_step(
                key="read-crdb",
                result={
                    "default_db_config": {"name": "orders", "memory_size": 104857600},
                    "causal_consistency": False,
                    "encryption": True,
                    "featureset_version": 12,
                    "protocol_version": 1,
                    "instances": [
                        {"cluster_url": TLV_URL, "id": 2, "compression": 3},
                        {"cluster_url": NY_URL, "id": 1, "compression": 3},
                    ],
                },
            ),
        ],
    )
    database: object = translator.operation_from_ended_record(
        trace_id="trace-1",
        prepared_creation=WITH_A_USER,
        record=record,
        interruption_error=INTERRUPTION_ERROR,
    ).database
    assert isinstance(database, ActiveActiveDatabaseResult)
    return database


def test_an_active_active_result_has_the_settings_the_crdb_stored(
    translator: CreationOutcomeTranslator[PreparedActiveActiveCreation],
) -> None:
    result: ActiveActiveDatabaseResult = created(translator=translator)

    assert (result.kind, str(result.crdb.guid), result.crdb.encryption, result.crdb.default_db_config) == (
        "active_active",
        GUID,
        True,
        {"name": "orders", "memory_size": 104857600},
    )


def test_an_active_active_result_has_one_branch_per_cluster_in_request_order(
    translator: CreationOutcomeTranslator[PreparedActiveActiveCreation],
) -> None:
    result: ActiveActiveDatabaseResult = created(translator=translator)

    assert [(cluster.cluster, cluster.db.db_uid) for cluster in result.clusters] == [
        (NY_FQDN, 7),
        (TLV_FQDN, 4),
    ]


def test_each_cluster_gets_the_crdb_instance_with_its_own_url(
    translator: CreationOutcomeTranslator[PreparedActiveActiveCreation],
) -> None:
    result: ActiveActiveDatabaseResult = created(translator=translator)

    assert [(cluster.cluster_url, cluster.instance_id) for cluster in result.clusters] == [
        (NY_URL, 1),
        (TLV_URL, 2),
    ]


def test_each_cluster_reads_its_users_from_the_steps_on_that_site(
    translator: CreationOutcomeTranslator[PreparedActiveActiveCreation],
) -> None:
    result: ActiveActiveDatabaseResult = created(translator=translator)

    assert [
        [(user.acl_uid, user.role_uid, user.user_uid) for user in cluster.db.permissions]
        for cluster in result.clusters
    ] == [[(10, 11, 12)], [(20, 21, 22)]]
