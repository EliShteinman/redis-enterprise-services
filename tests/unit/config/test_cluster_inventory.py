import pytest
from pydantic import TypeAdapter, ValidationError

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster, ConfiguredClusters


def configured_cluster(*, name: str) -> ConfiguredCluster:
    return ConfiguredCluster(
        name=name,
        network="net-a",
        environment="PROD",
        site="dc1",
        type="generic",
        api_url=f"https://{name}:9443",
    )


def test_a_cluster_configured_twice_is_refused_when_the_config_loads() -> None:
    with pytest.raises(expected_exception=ValidationError):
        TypeAdapter(ConfiguredClusters).validate_python(
            [configured_cluster(name="c1"), configured_cluster(name="c1")]
        )
