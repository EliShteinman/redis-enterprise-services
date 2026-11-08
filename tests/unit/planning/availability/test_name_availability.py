import pytest
from pydantic import SecretStr

from redis_enterprise_services.cluster.cluster_target_resolver import SharedCredentialsTargetResolver
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.exceptions.planning import NameTakenError
from redis_enterprise_services.planning.availability.listed_name_lookup import ListedNameLookup
from redis_enterprise_services.planning.availability.name_availability import NameAvailability
from redis_enterprise_services.planning.availability.name_lookups_by_kind import NameLookupsByKind
from redis_enterprise_services.planning.availability.requested_name import RequestedName
from redis_enterprise_services.resources.models import NamedResource


class CountingLister:
    def __init__(self, *, url_name_pairs: set[tuple[str, str]]) -> None:
        self._url_name_pairs: set[tuple[str, str]] = url_name_pairs
        self.calls: int = 0

    def list_uids_and_names(self, *, target: ClusterTarget) -> list[NamedResource]:
        self.calls += 1
        return [
            NamedResource(uid=1, name=name)
            for url, name in sorted(self._url_name_pairs)
            if url == target.api_url
        ]


def cluster(*, name: str) -> ConfiguredCluster:
    return ConfiguredCluster(
        name=name, network="net-a", environment="PROD", site="dc1", type="generic", api_url=f"https://{name}"
    )


C1: ConfiguredCluster = cluster(name="c1")
C2: ConfiguredCluster = cluster(name="c2")
NAMES: list[RequestedName] = [
    RequestedName(kind="database", name="orders"),
    RequestedName(kind="user", name="app"),
]


def lookup(*, lister: CountingLister) -> ListedNameLookup:
    return ListedNameLookup(lister=lister)


def availability(
    *, database_url_name_pairs: set[tuple[str, str]], user_lister: CountingLister
) -> NameAvailability:
    return NameAvailability(
        lookups=NameLookupsByKind(
            database=lookup(lister=CountingLister(url_name_pairs=database_url_name_pairs)),
            acl=lookup(lister=CountingLister(url_name_pairs=set())),
            role=lookup(lister=CountingLister(url_name_pairs=set())),
            user=lookup(lister=user_lister),
        ),
        target_resolver=SharedCredentialsTargetResolver(
            credentials=ClusterCredentials(username="admin", password=SecretStr("secret"))
        ),
    )


def test_names_missing_from_every_cluster_are_free() -> None:
    assert (
        availability(
            database_url_name_pairs=set(), user_lister=CountingLister(url_name_pairs=set())
        ).find_taken_names(clusters=[C1, C2], names=NAMES)
        == []
    )


def test_each_taken_name_is_reported_with_its_cluster() -> None:
    name_availability: NameAvailability = availability(
        database_url_name_pairs={("https://c2", "orders")},
        user_lister=CountingLister(url_name_pairs={("https://c1", "app")}),
    )

    assert [
        name.describe() for name in name_availability.find_taken_names(clusters=[C1, C2], names=NAMES)
    ] == [
        "user app exists on c1",
        "database orders exists on c2",
    ]


def test_each_kind_is_listed_once_per_cluster() -> None:
    users: CountingLister = CountingLister(url_name_pairs=set())
    names: list[RequestedName] = [
        RequestedName(kind="user", name=name) for name in ("app", "report", "audit")
    ]

    availability(database_url_name_pairs=set(), user_lister=users).find_taken_names(
        clusters=[C1, C2], names=names
    )

    assert users.calls == 2


def test_a_name_is_looked_up_only_among_its_own_kind() -> None:
    name_availability: NameAvailability = availability(
        database_url_name_pairs={("https://c1", "app")}, user_lister=CountingLister(url_name_pairs=set())
    )

    assert name_availability.find_taken_names(clusters=[C1], names=NAMES) == []


def test_a_taken_name_refuses_the_request() -> None:
    with pytest.raises(expected_exception=NameTakenError):
        availability(
            database_url_name_pairs={("https://c1", "orders")},
            user_lister=CountingLister(url_name_pairs=set()),
        ).find_taken_and_raise_if_any(clusters=[C1], names=NAMES)
