from redis_enterprise_services.config.clusters_settings import ClusterEntry
from redis_enterprise_services.config.edge_settings import NetworkSettings


def networks_without_relay(
    *, clusters: list[ClusterEntry], networks: dict[str, NetworkSettings]
) -> list[str]:
    return sorted({cluster.network for cluster in clusters} - networks.keys())
