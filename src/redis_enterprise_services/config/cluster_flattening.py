from collections.abc import Iterator
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, JsonValue

from redis_enterprise_services.config.base_url import comparable_url
from redis_enterprise_services.config.cluster_credentials_settings import ClusterCredentialsSettings
from redis_enterprise_services.config.cluster_fqdn import api_url_of
from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster, Environment
from redis_enterprise_services.config.cluster_tree_entries import (
    ClusterEntry,
    EnvironmentEntries,
    TreeEnvironment,
)
from redis_enterprise_services.config.level_values import ClusterValues, SharedLevelValues
from redis_enterprise_services.config.repeated_values import reject_repeated

ENVIRONMENT_OF_TREE_KEY: dict[TreeEnvironment, Environment] = {"dev": "DEV", "prod": "PROD", "test": "TEST"}


class ClusterInTree(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    environment: Environment
    network: str
    site: str
    fqdn: str
    levels_above: list[SharedLevelValues]
    entry: ClusterEntry

    def levels(self) -> list[SharedLevelValues | ClusterValues]:
        return [*self.levels_above, self.entry]


def configured_clusters(*, tree: EnvironmentEntries) -> list[ConfiguredCluster]:
    clusters: list[ConfiguredCluster] = [configured_cluster(cluster=cluster) for cluster in walk(tree=tree)]
    reject_repeated(what="cluster FQDNs", values=[cluster.fqdn.lower() for cluster in clusters])
    reject_repeated(
        what="cluster API URLs", values=[comparable_url(url=cluster.api_url) for cluster in clusters]
    )
    return clusters


def walk(*, tree: EnvironmentEntries) -> Iterator[ClusterInTree]:
    for environment_key, environment in tree.items():
        for network_name, network in environment.networks.items():
            for site_name, site in network.sites.items():
                for fqdn, entry in site.clusters.items():
                    yield ClusterInTree(
                        environment=ENVIRONMENT_OF_TREE_KEY[environment_key],
                        network=network_name,
                        site=site_name,
                        fqdn=fqdn,
                        levels_above=[environment, network, site],
                        entry=entry,
                    )


def configured_cluster(*, cluster: ClusterInTree) -> ConfiguredCluster:
    levels: list[SharedLevelValues | ClusterValues] = cluster.levels()
    return ConfiguredCluster(
        fqdn=cluster.fqdn,
        environment=cluster.environment,
        network=cluster.network,
        site=cluster.site,
        type=cluster.entry.type,
        api_url=api_url_of(
            fqdn=cluster.fqdn, api_port=lowest_set(values=[level.api_port for level in levels])
        ),
        credentials=ClusterCredentialsSettings(
            username=required(
                value=lowest_set(values=[level.username for level in levels]),
                fqdn=cluster.fqdn,
                setting="username",
            ),
            password=required(
                value=lowest_set(values=[level.password for level in levels]),
                fqdn=cluster.fqdn,
                setting="password",
            ),
        ),
        default_user_password=required(
            value=lowest_set(values=[level.default_user_password for level in levels]),
            fqdn=cluster.fqdn,
            setting="default_user_password",
        ),
        database_overrides=merged(layers=[level.database for level in levels]),
        active_active_database_overrides=merged(layers=[level.active_active.database for level in levels]),
        crdb_overrides=merged(layers=[level.active_active.crdb for level in cluster.levels_above]),
    )


def lowest_set[T](*, values: list[T | None]) -> T | None:
    return next((value for value in reversed(values) if value is not None), None)


def required[T](*, value: T | None, fqdn: str, setting: str) -> T:
    if value is None:
        raise ValueError(f"cluster {fqdn} has no {setting}: set it on the cluster or on a level above it")
    return value


def merged(*, layers: list[dict[str, JsonValue]]) -> dict[str, JsonValue]:
    values: dict[str, JsonValue] = {}
    for layer in layers:
        values.update(layer)
    return values
