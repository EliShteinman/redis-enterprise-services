from pydantic import SecretStr

from redis_enterprise_services.config.clusters.cluster_credentials_settings import ClusterCredentialsSettings
from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.creation.results.crdb_instance_of_cluster import crdb_instance_of_cluster
from redis_enterprise_services.steps.crdb.read_crdb import CrdbInstanceSettings

CLUSTER: ConfiguredCluster = ConfiguredCluster(
    fqdn="cluster-a.example.com",
    network="net-a",
    environment="PROD",
    site="ny",
    type="generic",
    api_url="https://cluster-a.example.com",
    credentials=ClusterCredentialsSettings(username="admin", password=SecretStr("secret")),
    default_user_password=SecretStr("default-user-secret"),
)


def test_an_instance_is_matched_to_its_cluster_by_the_same_url_written_differently() -> None:
    instance: CrdbInstanceSettings = CrdbInstanceSettings(
        cluster_url="https://Cluster-A.example.com:443", id=1, compression=6
    )

    assert crdb_instance_of_cluster(cluster=CLUSTER, instances=[instance]) == instance
