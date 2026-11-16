from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.repeated_values import repeated_values
from redis_enterprise_services.crdbs.creation_body import cluster_fqdn
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.exceptions.planning import DuplicateSitesError, MixedNetworksError


def reject_clusters_that_cannot_share_a_crdb(*, clusters: list[ConfiguredCluster]) -> None:
    reject_mixed_networks(clusters=clusters)
    reject_sites_on_one_cluster(clusters=clusters)
    reject_clusters_that_clash(clusters=clusters)
    reject_different_default_user_passwords(clusters=clusters)


def reject_mixed_networks(*, clusters: list[ConfiguredCluster]) -> None:
    networks: set[str] = {cluster.network for cluster in clusters}
    if len(networks) > 1:
        raise MixedNetworksError(message=f"the sites are on more than one network: {sorted(networks)}")


def reject_sites_on_one_cluster(*, clusters: list[ConfiguredCluster]) -> None:
    repeated: set[str] = repeated_values(values=[cluster.api_url for cluster in clusters])
    if repeated:
        raise DuplicateSitesError(
            message=f"more than one site resolves to the same cluster: {sorted(repeated)}"
        )


def reject_clusters_that_clash(*, clusters: list[ConfiguredCluster]) -> None:
    for kind, values in (
        ("FQDN", [cluster.fqdn for cluster in clusters]),
        ("host", [cluster_fqdn(api_url=cluster.api_url) for cluster in clusters]),
    ):
        repeated: set[str] = repeated_values(values=values)
        if repeated:
            raise ConfigurationError(
                message=f"different clusters of one Active-Active database share a {kind}: {sorted(repeated)}"
            )


def reject_different_default_user_passwords(*, clusters: list[ConfiguredCluster]) -> None:
    if len({cluster.default_user_password.get_secret_value() for cluster in clusters}) > 1:
        raise ConfigurationError(
            message="the clusters of one Active-Active database must have the same default_user_password, "
            f"and {[cluster.fqdn for cluster in clusters]} do not"
        )
