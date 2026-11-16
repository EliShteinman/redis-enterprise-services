import pytest
from pydantic import JsonValue, TypeAdapter, ValidationError

from redis_enterprise_services.config.clusters.cluster_flattening import configured_clusters
from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.clusters.cluster_tree import ClusterTree

TREE: TypeAdapter[ClusterTree] = TypeAdapter(ClusterTree)
SECRETS: dict[str, JsonValue] = {
    "username": "admin",
    "password": "admin-secret",
    "default_user_password": "default-user-secret",
}
API_SCHEME: str = "https"


def a_cluster(**values: JsonValue) -> dict[str, JsonValue]:
    return {"type": "generic", **values}


def tree_data(
    *,
    environment: dict[str, JsonValue] | None = None,
    network: dict[str, JsonValue] | None = None,
    site: dict[str, JsonValue] | None = None,
    clusters: dict[str, JsonValue] | None = None,
) -> dict[str, JsonValue]:
    return {
        "prod": {
            "api_port": 9443,
            **SECRETS,
            **(environment or {}),
            "networks": {
                "net-a": {
                    **(network or {}),
                    "sites": {"dc1": {**(site or {}), "clusters": clusters or {"c1.net-a": a_cluster()}}},
                }
            },
        }
    }


def a_tree(
    *,
    environment: dict[str, JsonValue] | None = None,
    network: dict[str, JsonValue] | None = None,
    site: dict[str, JsonValue] | None = None,
    clusters: dict[str, JsonValue] | None = None,
) -> ClusterTree:
    return TREE.validate_python(
        tree_data(environment=environment, network=network, site=site, clusters=clusters)
    )


def only_cluster(*, tree: ClusterTree) -> ConfiguredCluster:
    [configured] = configured_clusters(tree=tree, api_scheme=API_SCHEME)
    return configured


def test_a_cluster_gets_its_environment_network_and_site_from_its_place_in_the_tree() -> None:
    configured: ConfiguredCluster = only_cluster(tree=a_tree())

    assert (configured.fqdn, configured.environment, configured.network, configured.site) == (
        "c1.net-a",
        "PROD",
        "net-a",
        "dc1",
    )


@pytest.mark.parametrize(
    argnames=("fqdn", "expected"),
    argvalues=[
        pytest.param("c1.net-a", "https://c1.net-a:9443", id="the-api-port-of-its-levels"),
        pytest.param("c1.net-a:9444", "https://c1.net-a:9444", id="its-own-port"),
    ],
)
def test_the_api_url_of_a_cluster_is_built_from_its_fqdn(fqdn: str, expected: str) -> None:
    assert only_cluster(tree=a_tree(clusters={fqdn: a_cluster()})).api_url == expected


@pytest.mark.parametrize(
    argnames=("environment", "network", "site", "cluster", "expected"),
    argvalues=[
        pytest.param({"version": "7.4"}, {}, {}, {}, "7.4", id="environment"),
        pytest.param({"version": "7.4"}, {"version": "7.8"}, {}, {}, "7.8", id="network-beats-environment"),
        pytest.param(
            {"version": "7.4"}, {"version": "7.8"}, {"version": "8.0"}, {}, "8.0", id="site-beats-network"
        ),
        pytest.param(
            {"version": "7.4"},
            {"version": "7.8"},
            {"version": "8.0"},
            {"version": "8.2"},
            "8.2",
            id="cluster-beats-all",
        ),
    ],
)
def test_the_lowest_level_that_sets_a_database_value_wins(
    environment: dict[str, JsonValue],
    network: dict[str, JsonValue],
    site: dict[str, JsonValue],
    cluster: dict[str, JsonValue],
    expected: str,
) -> None:
    configured: ConfiguredCluster = only_cluster(
        tree=a_tree(
            environment={"database": environment},
            network={"database": network},
            site={"database": site},
            clusters={"c1.net-a": a_cluster(database=cluster)},
        )
    )

    assert configured.database_overrides["version"] == expected


def test_the_lowest_level_that_sets_a_secret_wins_for_each_secret_on_its_own() -> None:
    configured: ConfiguredCluster = only_cluster(
        tree=a_tree(
            network={"username": "net-admin", "default_user_password": "net-default"},
            site={"password": "site-secret"},
            clusters={"c1.net-a": a_cluster(username="c1-admin")},
        )
    )

    assert (
        configured.credentials.username,
        configured.credentials.password.get_secret_value(),
        configured.default_user_password.get_secret_value(),
    ) == ("c1-admin", "site-secret", "net-default")


@pytest.mark.parametrize(
    argnames="missing", argvalues=["username", "password", "default_user_password", "api_port"]
)
def test_a_cluster_without_a_value_it_needs_on_any_level_is_refused(missing: str) -> None:
    data: dict[str, JsonValue] = tree_data()
    environment: JsonValue = data["prod"]
    assert isinstance(environment, dict)
    del environment[missing]
    tree: ClusterTree = TREE.validate_python(data)

    with pytest.raises(expected_exception=ValueError, match=f"cluster c1.net-a has no {missing}"):
        configured_clusters(tree=tree, api_scheme=API_SCHEME)


@pytest.mark.parametrize(
    argnames="clusters",
    argvalues=[
        pytest.param({"generic": a_cluster(type="dedicated")}, id="dedicated-at-the-generic-fqdn"),
        pytest.param({"https://c1.net-a": a_cluster()}, id="url-instead-of-fqdn"),
        pytest.param({"c1.net-a": a_cluster(site="dc1")}, id="unknown-setting"),
    ],
)
def test_a_cluster_entry_that_cannot_be_used_is_refused_when_the_config_loads(
    clusters: dict[str, JsonValue],
) -> None:
    with pytest.raises(expected_exception=ValidationError):
        a_tree(clusters=clusters)


@pytest.mark.parametrize(
    argnames=("first_fqdn", "second_fqdn"),
    argvalues=[
        pytest.param("c1.net-a", "C1.net-a", id="same-fqdn"),
        pytest.param("c1.net-a", "c1.net-a:9443", id="same-api-url"),
    ],
)
def test_the_same_cluster_twice_is_refused(first_fqdn: str, second_fqdn: str) -> None:
    tree: ClusterTree = a_tree(clusters={first_fqdn: a_cluster(), second_fqdn: a_cluster()})

    with pytest.raises(expected_exception=ValueError, match="configured more than once"):
        configured_clusters(tree=tree, api_scheme=API_SCHEME)


def test_the_same_fqdn_in_two_networks_is_refused() -> None:
    data: dict[str, JsonValue] = {
        "prod": {
            **SECRETS,
            "networks": {
                network: {"sites": {"dc1": {"clusters": {"c1:9443": a_cluster()}}}}
                for network in ("net-a", "net-b")
            },
        }
    }
    tree: ClusterTree = TREE.validate_python(data)

    with pytest.raises(expected_exception=ValueError, match="configured more than once"):
        configured_clusters(tree=tree, api_scheme=API_SCHEME)


def test_an_empty_tree_is_refused_when_the_config_loads() -> None:
    with pytest.raises(expected_exception=ValidationError):
        TREE.validate_python({})
