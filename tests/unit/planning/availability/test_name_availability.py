import pytest
from pydantic import SecretStr

from redis_enterprise_services.cluster.cluster_target_resolver import SharedCredentialsTargetResolver
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.cluster_inventory import ClusterEntry
from redis_enterprise_services.exceptions.planning import NameTakenError
from redis_enterprise_services.planning.availability.listed_name_lookup import ListedNameLookup
from redis_enterprise_services.planning.availability.name_availability import NameAvailability
from redis_enterprise_services.planning.availability.name_lookups import NameLookups
from redis_enterprise_services.planning.availability.requested_name import RequestedName
from redis_enterprise_services.resources.models import NamedResource


class CountingLister:
    def __init__(self, *, names: set[tuple[str, str]]) -> None:
        self._names: set[tuple[str, str]] = names
        self.calls: int = 0

    def list_named(self, *, target: ClusterTarget) -> list[NamedResource]:
        self.calls += 1
        return [NamedResource(uid=1, name=name) for url, name in sorted(self._names) if url == target.api_url]


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


def lookup(*, lister: CountingLister) -> ListedNameLookup:
    return ListedNameLookup(lister=lister)


def availability(*, databases: set[tuple[str, str]], users: CountingLister) -> NameAvailability:
    return NameAvailability(
        lookups=NameLookups(
            database=lookup(lister=CountingLister(names=databases)),
            acl=lookup(lister=CountingLister(names=set())),
            role=lookup(lister=CountingLister(names=set())),
            user=lookup(lister=users),
        ),
        credentials=SharedCredentialsTargetResolver(
            credentials=ClusterCredentials(username="admin", password=SecretStr("secret"))
        ),
    )


def test_names_missing_from_every_cluster_are_free() -> None:
    assert (
        availability(databases=set(), users=CountingLister(names=set())).taken(clusters=[C1, C2], names=NAMES)
        == []
    )


def test_each_taken_name_is_reported_with_its_cluster() -> None:
    checked: NameAvailability = availability(
        databases={("https://c2", "orders")}, users=CountingLister(names={("https://c1", "app")})
    )

    assert [name.describe() for name in checked.taken(clusters=[C1, C2], names=NAMES)] == [
        "user app exists on c1",
        "database orders exists on c2",
    ]


def test_each_kind_is_listed_once_per_cluster() -> None:
    users: CountingLister = CountingLister(names=set())
    names: list[RequestedName] = [
        RequestedName(kind="user", name=name) for name in ("app", "report", "audit")
    ]

    availability(databases=set(), users=users).taken(clusters=[C1, C2], names=names)

    assert users.calls == 2


def test_a_name_is_looked_up_only_among_its_own_kind() -> None:
    checked: NameAvailability = availability(
        databases={("https://c1", "app")}, users=CountingLister(names=set())
    )

    assert checked.taken(clusters=[C1], names=NAMES) == []


def test_a_taken_name_refuses_the_request() -> None:
    with pytest.raises(expected_exception=NameTakenError):
        availability(databases={("https://c1", "orders")}, users=CountingLister(names=set())).ensure_free(
            clusters=[C1], names=NAMES
        )
