import pytest
from pydantic import TypeAdapter, ValidationError

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster, ConfiguredClusters


def configured_cluster(*, name: str, site: str = "dc1", api_url: str | None = None) -> ConfiguredCluster:
    return ConfiguredCluster(
        name=name,
        network="net-a",
        environment="PROD",
        site=site,
        type="generic",
        api_url=api_url or f"https://{name}:9443",
    )


@pytest.mark.parametrize(
    argnames="clusters",
    argvalues=[
        pytest.param(
            [configured_cluster(name="c1"), configured_cluster(name="c1", api_url="https://other:9443")],
            id="same-network-environment-site-and-name",
        ),
        pytest.param(
            [configured_cluster(name="c1"), configured_cluster(name="c2", api_url="https://c1:9443")],
            id="same-api-url",
        ),
    ],
)
def test_a_cluster_configured_twice_is_refused_when_the_config_loads(
    clusters: list[ConfiguredCluster],
) -> None:
    with pytest.raises(expected_exception=ValidationError):
        TypeAdapter(ConfiguredClusters).validate_python(clusters)


def test_the_same_cluster_name_on_another_site_loads() -> None:
    clusters: list[ConfiguredCluster] = [
        configured_cluster(name="c1"),
        configured_cluster(name="c1", site="dc2", api_url="https://c1-dc2:9443"),
    ]

    assert TypeAdapter(ConfiguredClusters).validate_python(clusters) == clusters
