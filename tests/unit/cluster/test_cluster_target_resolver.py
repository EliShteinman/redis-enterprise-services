import pytest
from pydantic import SecretStr

from redis_enterprise_services.cluster.cluster_target_resolver import ConfiguredCredentialsTargetResolver
from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.cluster_access.cluster_credentials import ClusterCredentials
from redis_enterprise_services.exceptions.configuration import ConfigurationError

C1_ADMIN: ClusterCredentials = ClusterCredentials(username="c1-admin", password=SecretStr("c1-secret"))
C2_ADMIN: ClusterCredentials = ClusterCredentials(username="c2-admin", password=SecretStr("c2-secret"))
CLUSTER_1: ClusterAddress = ClusterAddress(network="net-a", api_url="https://c1:9443")
CLUSTER_2: ClusterAddress = ClusterAddress(network="net-a", api_url="https://c2:9443")
RESOLVER: ConfiguredCredentialsTargetResolver = ConfiguredCredentialsTargetResolver(
    credentials_by_api_url={CLUSTER_1.api_url: C1_ADMIN, CLUSTER_2.api_url: C2_ADMIN}
)


def test_every_cluster_is_called_with_its_own_credentials() -> None:
    assert [RESOLVER.target_for(address=address).credentials for address in (CLUSTER_1, CLUSTER_2)] == [
        C1_ADMIN,
        C2_ADMIN,
    ]


def test_a_cluster_that_is_not_in_the_cluster_file_is_refused() -> None:
    with pytest.raises(expected_exception=ConfigurationError):
        RESOLVER.target_for(address=ClusterAddress(network="net-a", api_url="https://c3:9443"))
