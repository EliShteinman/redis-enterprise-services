from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster


def address_of(*, cluster: ConfiguredCluster) -> ClusterAddress:
    return ClusterAddress(network=cluster.network, api_url=cluster.api_url)
