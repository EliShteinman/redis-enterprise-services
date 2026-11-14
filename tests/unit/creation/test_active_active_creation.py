from unittest.mock import MagicMock, create_autospec

import pytest
from pydantic import JsonValue

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.operation_settings import OperationSettings
from redis_enterprise_services.config.settings import load_settings
from redis_enterprise_services.config.user_resources_settings import UserResourcesSettings
from redis_enterprise_services.creation.create_database_request import CreateDatabaseRequest
from redis_enterprise_services.creation.creation_outcome_translator import CreationOutcomeTranslator
from redis_enterprise_services.creation.creation_preparation import CreationPreparation
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.exceptions.planning import MixedNetworksError
from redis_enterprise_services.operations.public_errors import PublicErrors
from redis_enterprise_services.operations.remaining_resource import RemainingResource
from redis_enterprise_services.planning.database_defaults import DatabaseDefaults
from redis_enterprise_services.planning.database_spec import DatabaseSpec, DatabaseUserSpec
from redis_enterprise_services.planning.naming.name_validator import NameValidator
from redis_enterprise_services.planning.naming.user_names_validator import UserNamesValidator
from redis_enterprise_services.planning.site_cluster_resolver import SiteClusterResolver
from redis_enterprise_services.planning.user_resource_naming import UserResourceNaming
from redis_enterprise_services.saga.contract.saga_record import SagaRecord, SagaStatus, StepRecord, StepStatus
from redis_enterprise_services.saga.contract.step_kind import StepKind

C1: ConfiguredCluster = ConfiguredCluster(
    name="c1", network="net-a", environment="DEV", site="dc1", type="generic", api_url="https://c1:9443"
)
C2: ConfiguredCluster = ConfiguredCluster(
    name="c2", network="net-a", environment="DEV", site="dc2", type="generic", api_url="https://c2:9443"
)
C3_OTHER_NETWORK: ConfiguredCluster = C2.model_copy(update={"name": "c3", "network": "net-b"})
DATABASE: NewDatabase = NewDatabase(name="orders", memory_size=104857600)
REQUEST: CreateDatabaseRequest = CreateDatabaseRequest.model_validate(
    obj={
        "target": {
            "active_active": True,
            "sites": [
                {"network": "net-a", "site": "dc1", "environment": "DEV", "cluster": "generic"},
                {"network": "net-a", "site": "dc2", "environment": "DEV", "cluster": "generic"},
            ],
        },
        "spec": {"database": {"name": "orders", "memory_size": 104857600}},
    }
)


def preparation(*, clusters: list[ConfiguredCluster], filled: list[NewDatabase]) -> CreationPreparation:
    resolver: MagicMock = create_autospec(spec=SiteClusterResolver, instance=True)
    resolver.resolve.side_effect = clusters
    defaults: MagicMock = create_autospec(spec=DatabaseDefaults, instance=True)
    defaults.fill_in.side_effect = filled
    return CreationPreparation(
        name_validator=create_autospec(spec=NameValidator, instance=True),
        user_names_validator=create_autospec(spec=UserNamesValidator, instance=True),
        site_cluster_resolver=resolver,
        database_defaults=defaults,
    )


def test_an_active_active_creation_is_prepared_on_every_site() -> None:
    prepared: PreparedCreation = preparation(clusters=[C1, C2], filled=[DATABASE, DATABASE]).prepare(
        creation_request=REQUEST
    )

    assert (prepared.active_active, [cluster.name for cluster in prepared.clusters]) == (True, ["c1", "c2"])


def test_sites_on_more_than_one_network_are_refused() -> None:
    with pytest.raises(expected_exception=MixedNetworksError):
        preparation(clusters=[C1, C3_OTHER_NETWORK], filled=[DATABASE, DATABASE]).prepare(
            creation_request=REQUEST
        )


def test_defaults_that_differ_between_sites_are_a_configuration_error() -> None:
    other: NewDatabase = DATABASE.model_copy(update={"replication": True})

    with pytest.raises(expected_exception=ConfigurationError):
        preparation(clusters=[C1, C2], filled=[DATABASE, other]).prepare(creation_request=REQUEST)


def test_a_single_site_database_on_two_sites_is_refused() -> None:
    body: dict[str, JsonValue] = REQUEST.model_dump(mode="json")
    body["target"]["active_active"] = False  # type: ignore[index]

    with pytest.raises(expected_exception=ValueError):
        CreateDatabaseRequest.model_validate(obj=body)


def step_record(*, key: str, status: StepStatus, result: JsonValue) -> StepRecord:
    return StepRecord(key=key, kind=StepKind.COMPENSATABLE, status=status, result=result)


def remaining_after_manual_intervention() -> list[RemainingResource]:
    acl: JsonValue = {"uid": 21, "name": "orders-app-acl", "action_uid": None, "fields": {}}
    record: SagaRecord = SagaRecord(
        saga_id="trace-1",
        status=SagaStatus.REQUIRES_MANUAL_INTERVENTION,
        steps=[
            step_record(key="crdb", status=StepStatus.DONE, result={"guid": "g-1"}),
            step_record(key="c2/acl/app", status=StepStatus.COMPENSATION_FAILED, result=acl),
        ],
        stopped_at="c2/acl/app",
    )
    users: UserResourcesSettings = UserResourcesSettings(
        acl_name_template="{database}-{user}-acl",
        role_name_template="{database}-{user}-role",
        role_management="db_viewer",
    )
    return CreationOutcomeTranslator(
        resource_naming=UserResourceNaming(settings=users),
        database_settings=load_settings().database,
        public_errors=PublicErrors(
            settings=OperationSettings(
                public_code_by_internal_code={},
                public_codes_with_cluster_details=frozenset(),
                error_kind_by_code={},
            ),
            internal_error_message="internal error",
            unexpected_error_message="unexpected {error_type}: {error}",
        ),
    ).remaining_resources(
        prepared_creation=PreparedCreation(
            clusters=[C1, C2],
            active_active=True,
            spec=DatabaseSpec(
                database=DATABASE,
                users=[DatabaseUserSpec(name="app", password="p1-passw0rd", acl_rule="+@all ~orders:*")],
            ),
        ),
        record=record,
    )


def test_a_crdb_left_behind_is_reported_on_the_coordinator_with_its_guid() -> None:
    crdb: RemainingResource = remaining_after_manual_intervention()[0]

    assert (crdb.resource_type, crdb.cluster_url, crdb.crdb_guid) == ("crdb", "https://c1:9443", "g-1")


def test_a_user_resource_left_behind_is_reported_on_its_own_site() -> None:
    acl: RemainingResource = remaining_after_manual_intervention()[1]

    assert (acl.resource_type, acl.cluster_url, acl.uid) == ("acl", "https://c2:9443", 21)
