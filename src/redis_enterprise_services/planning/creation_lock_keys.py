from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.planning.database_spec import DatabaseSpec
from redis_enterprise_services.planning.lock_keys import database_lock_key, user_lock_key


def creation_lock_keys(*, clusters: list[ConfiguredCluster], spec: DatabaseSpec) -> list[str]:
    return [key for cluster in clusters for key in lock_keys_on_cluster(cluster=cluster, spec=spec)]


def lock_keys_on_cluster(*, cluster: ConfiguredCluster, spec: DatabaseSpec) -> list[str]:
    return [
        database_lock_key(cluster_url=cluster.api_url, database_name=spec.database.name),
        *(user_lock_key(cluster_url=cluster.api_url, user_name=user.name) for user in spec.users),
    ]
