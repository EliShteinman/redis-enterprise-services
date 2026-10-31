import pytest
from pydantic import SecretStr

from redis_enterprise_services.cluster.credentials import SharedCredentialsProvider
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.config.clusters_settings import ClusterEntry
from redis_enterprise_services.config.decomposition_settings import DecompositionSettings
from redis_enterprise_services.connection.models import ClusterCredentials
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.exceptions.planning import NameTakenError
from redis_enterprise_services.planning.availability.creation_names import CreationNames
from redis_enterprise_services.planning.availability.name_availability import NameAvailability
from redis_enterprise_services.planning.availability.requested_name import RequestedName
from redis_enterprise_services.planning.database_request import DatabaseRequest, DatabaseUserRequest
from redis_enterprise_services.planning.resource_names import ResourceNames


class ExistingNames:
    def __init__(self, *, names: set[tuple[str, str]]) -> None:
        self._names: set[tuple[str, str]] = names

    def exists(self, *, target: ClusterTarget, name: str) -> bool:
        return (target.api_url, name) in self._names


def cluster(*, name: str) -> ClusterEntry:
    return ClusterEntry(
        name=name, network="net-a", environment="PROD", site="dc1", type="generic", api_url=f"https://{name}"
    )


C1: ClusterEntry = cluster(name="c1")
C2: ClusterEntry = cluster(name="c2")
NAMES: list[RequestedName] = [
    RequestedName(kind="database", name="orders"),
    RequestedName(kind="user", name="app"),
]


def availability(*, databases: set[tuple[str, str]], users: set[tuple[str, str]]) -> NameAvailability:
    return NameAvailability(
        lookups={
            "database": ExistingNames(names=databases),
            "acl": ExistingNames(names=set()),
            "role": ExistingNames(names=set()),
            "user": ExistingNames(names=users),
        },
        credentials=SharedCredentialsProvider(
            credentials=ClusterCredentials(username="admin", password=SecretStr("secret"))
        ),
    )


def test_names_missing_from_every_cluster_are_free() -> None:
    assert availability(databases=set(), users=set()).taken(clusters=[C1, C2], names=NAMES) == []


def test_each_taken_name_is_reported_with_its_cluster() -> None:
    checked: NameAvailability = availability(
        databases={("https://c2", "orders")}, users={("https://c1", "app")}
    )

    assert [name.describe() for name in checked.taken(clusters=[C1, C2], names=NAMES)] == [
        "user app exists on c1",
        "database orders exists on c2",
    ]


def test_a_name_is_looked_up_only_among_its_own_kind() -> None:
    checked: NameAvailability = availability(databases={("https://c1", "app")}, users=set())

    assert checked.taken(clusters=[C1], names=NAMES) == []


def test_a_taken_name_refuses_the_request() -> None:
    with pytest.raises(expected_exception=NameTakenError):
        availability(databases={("https://c1", "orders")}, users=set()).ensure_free(
            clusters=[C1], names=NAMES
        )


def test_a_creation_checks_the_database_and_each_user_with_its_derived_names() -> None:
    names: CreationNames = CreationNames(
        names=ResourceNames(
            settings=DecompositionSettings(
                acl_name="{database}-{user}-acl",
                role_name="{database}-{user}-role",
                role_management="db_viewer",
            )
        )
    )
    request: DatabaseRequest = DatabaseRequest(
        database=NewDatabase(name="orders", memory_size=104857600),
        users=[DatabaseUserRequest(name="app", password="p1", acl="+@all")],
    )

    assert [(name.kind, name.name) for name in names.of(request=request)] == [
        ("database", "orders"),
        ("acl", "orders-app-acl"),
        ("role", "orders-app-role"),
        ("user", "app"),
    ]
