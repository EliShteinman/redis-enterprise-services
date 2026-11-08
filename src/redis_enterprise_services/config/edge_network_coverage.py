from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.edge_settings import EdgeNetworkSettings


def networks_missing_from_edge(
    *, clusters: list[ConfiguredCluster], networks: dict[str, EdgeNetworkSettings]
) -> list[str]:
    return sorted({cluster.network for cluster in clusters} - networks.keys())
