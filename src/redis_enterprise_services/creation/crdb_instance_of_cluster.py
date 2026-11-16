from redis_enterprise_services.config.base_url import is_same_url
from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.exceptions.cluster import IncompleteClusterObjectError
from redis_enterprise_services.steps.read_crdb import CrdbInstanceSettings


def crdb_instance_of_cluster(
    *, cluster: ConfiguredCluster, instances: list[CrdbInstanceSettings]
) -> CrdbInstanceSettings:
    for instance in instances:
        if is_same_url(url=instance.cluster_url, other_url=cluster.api_url):
            return instance
    raise IncompleteClusterObjectError(message=f"the CRDB has no instance on cluster {cluster.api_url}")
