from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.exceptions.cluster import IncompleteClusterObjectError
from redis_enterprise_services.steps.read_crdb import CrdbInstanceSettings


def crdb_instance_of_cluster(
    *, cluster: ConfiguredCluster, instances: list[CrdbInstanceSettings]
) -> CrdbInstanceSettings:
    for instance in instances:
        if instance.cluster_url == cluster.api_url:
            return instance
    raise IncompleteClusterObjectError(message=f"the CRDB has no instance on cluster {cluster.api_url}")
