import pytest
from pydantic import SecretStr

from redis_enterprise_services.cluster.cluster_target_resolver import ConfiguredCredentialsTargetResolver
from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.config.cluster_credentials_settings import ClusterCredentialsSettings
from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.exceptions.cluster import UnreadableClusterResponseError
from redis_enterprise_services.exceptions.planning import NameTakenError
from redis_enterprise_services.planning.availability.listed_name_lookup import ListedNameLookup
from redis_enterprise_services.planning.availability.name_availability import NameAvailability
from redis_enterprise_services.planning.availability.name_lookups_by_kind import NameLookupsByKind
from redis_enterprise_services.planning.availability.requested_name import RequestedName
from redis_enterprise_services.resources.models import ClusterObject


class CountingLister:
    def __init__(self, *, url_name_pairs: set[tuple[str, str]]) -> None:
        self._url_name_pairs: set[tuple[str, str]] = url_name_pairs
        self.calls: int = 0

    def list_objects(self, *, target: ClusterTarget) -> list[ClusterObject]:
        self.calls += 1
        return [
            ClusterObject(uid=1, name=name, fields={"uid": 1, "name": name})
            for url, name in sorted(self._url_name_pairs)
            if url == target.api_url
        ]


ADMIN: ClusterCredentials = ClusterCredentials(username="admin", password=SecretStr("secret"))


def cluster(*, fqdn: str) -> ConfiguredCluster:
    return ConfiguredCluster(
        fqdn=fqdn,
        network="net-a",
        environment="PROD",
        site="ny",
        type="generic",
        api_url=f"https://{fqdn}",
        credentials=ClusterCredentialsSettings(username=ADMIN.username, password=ADMIN.password),
        default_user_password=SecretStr("default-user-secret"),
    )


C1: ConfiguredCluster = cluster(fqdn="c1")
C2: ConfiguredCluster = cluster(fqdn="c2")
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
        target_resolver=ConfiguredCredentialsTargetResolver(
            credentials_by_api_url={configured.api_url: ADMIN for configured in (C1, C2)}
        ),
    )


def test_names_missing_from_every_cluster_are_free() -> None:
    assert (
        availability(
            database_url_name_pairs=set(), user_lister=CountingLister(url_name_pairs=set())
        ).find_taken_names(clusters=[C1, C2], requested_names=NAMES)
        == []
    )


def test_each_taken_name_is_reported_with_its_cluster() -> None:
    name_availability: NameAvailability = availability(
        database_url_name_pairs={("https://c2", "orders")},
        user_lister=CountingLister(url_name_pairs={("https://c1", "app")}),
    )

    assert [
        taken_name.describe()
        for taken_name in name_availability.find_taken_names(clusters=[C1, C2], requested_names=NAMES)
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
        clusters=[C1, C2], requested_names=names
    )

    assert users.calls == 2


def test_a_name_is_looked_up_only_among_its_own_kind() -> None:
    name_availability: NameAvailability = availability(
        database_url_name_pairs={("https://c1", "app")}, user_lister=CountingLister(url_name_pairs=set())
    )

    assert name_availability.find_taken_names(clusters=[C1], requested_names=NAMES) == []


def test_a_taken_name_refuses_the_request() -> None:
    with pytest.raises(expected_exception=NameTakenError):
        availability(
            database_url_name_pairs={("https://c1", "orders")},
            user_lister=CountingLister(url_name_pairs=set()),
        ).ensure_free(clusters=[C1], requested_names=NAMES)


class UnreadableOnC2Lister(CountingLister):
    def list_objects(self, *, target: ClusterTarget) -> list[ClusterObject]:
        if target.api_url == C2.api_url:
            raise UnreadableClusterResponseError(message="the list came back unreadable")
        return super().list_objects(target=target)


def test_a_lookup_that_fails_on_one_site_names_that_site() -> None:
    with pytest.raises(expected_exception=UnreadableClusterResponseError) as failure:
        availability(
            database_url_name_pairs=set(), user_lister=UnreadableOnC2Lister(url_name_pairs=set())
        ).ensure_free(clusters=[C1, C2], requested_names=NAMES)

    assert failure.value.cluster_url == C2.api_url
