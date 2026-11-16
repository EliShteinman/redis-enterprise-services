from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster


def coordinator_of(*, clusters: list[ConfiguredCluster]) -> ConfiguredCluster:
    return clusters[0]
