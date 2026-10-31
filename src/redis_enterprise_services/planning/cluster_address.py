from redis_enterprise_services.cluster.models import ClusterAddress
from redis_enterprise_services.config.clusters_settings import ClusterEntry


def address_of(*, cluster: ClusterEntry) -> ClusterAddress:
    return ClusterAddress(network=cluster.network, api_url=cluster.api_url)
