from redis_enterprise_services.config.clusters_settings import ClusterEntry
from redis_enterprise_services.config.edge_settings import EdgeNetworkSettings


def networks_missing_from_edge(
    *, clusters: list[ClusterEntry], networks: dict[str, EdgeNetworkSettings]
) -> list[str]:
    return sorted({cluster.network for cluster in clusters} - networks.keys())
