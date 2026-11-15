import logging

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.crdbs.creation_body import cluster_fqdn
from redis_enterprise_services.creation.create_database_request import CreateDatabaseRequest
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.databases.new_database import PERSISTENCE_MODE_BY_FIELD, NewDatabase
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.exceptions.planning import DuplicateSitesError, MixedNetworksError
from redis_enterprise_services.planning.database_defaults import DATA_PERSISTENCE_FIELD, DatabaseDefaults
from redis_enterprise_services.planning.naming.name_validator import NameValidator
from redis_enterprise_services.planning.naming.naming_context import NamingContext
from redis_enterprise_services.planning.naming.user_names_validator import UserNamesValidator
from redis_enterprise_services.planning.site_cluster_resolver import SiteClusterResolver

logger: logging.Logger = logging.getLogger(name=__name__)


class CreationPreparation:
    def __init__(
        self,
        *,
        name_validator: NameValidator,
        user_names_validator: UserNamesValidator,
        site_cluster_resolver: SiteClusterResolver,
        database_defaults: DatabaseDefaults,
    ) -> None:
        self._name_validator: NameValidator = name_validator
        self._user_names_validator: UserNamesValidator = user_names_validator
        self._site_cluster_resolver: SiteClusterResolver = site_cluster_resolver
        self._database_defaults: DatabaseDefaults = database_defaults

    def prepare(self, *, creation_request: CreateDatabaseRequest) -> PreparedCreation:
        requested_database: NewDatabase = creation_request.spec.database
        context: NamingContext = creation_request.target.naming_context()
        self._name_validator.ensure_valid(name=requested_database.name, context=context)
        self._user_names_validator.ensure_valid(spec=creation_request.spec, context=context)
        clusters: list[ConfiguredCluster] = [
            self._site_cluster_resolver.resolve(placement=site) for site in creation_request.target.sites
        ]
        reject_mixed_networks(clusters=clusters)
        reject_sites_on_one_cluster(clusters=clusters)
        reject_clusters_that_clash(clusters=clusters)
        filled_database: NewDatabase = self._same_database_on_every_site(
            clusters=clusters,
            requested=requested_database,
            active_active=creation_request.target.active_active,
        )
        logger.info(
            msg=f"creating {filled_database.name} on {[cluster.name for cluster in clusters]} is prepared"
        )
        return PreparedCreation(
            clusters=clusters,
            active_active=creation_request.target.active_active,
            spec=creation_request.spec.with_database(database=filled_database),
        )

    def _same_database_on_every_site(
        self, *, clusters: list[ConfiguredCluster], requested: NewDatabase, active_active: bool
    ) -> NewDatabase:
        filled: list[NewDatabase] = [
            self._database_defaults.fill_in(cluster=cluster, requested=requested, active_active=active_active)
            for cluster in clusters
        ]
        differing: list[str] = fields_to_send(
            differing=[
                name
                for name in NewDatabase.model_fields
                if any(getattr(database, name) != getattr(filled[0], name) for database in filled)
            ]
        )
        if differing:
            raise ConfigurationError(
                message=f"the database defaults give {differing} different values on "
                f"{[cluster.name for cluster in clusters]}"
            )
        return filled[0]


def fields_to_send(*, differing: list[str]) -> list[str]:
    if DATA_PERSISTENCE_FIELD in differing:
        return sorted(name for name in differing if name not in PERSISTENCE_MODE_BY_FIELD)
    return sorted(differing)


def reject_mixed_networks(*, clusters: list[ConfiguredCluster]) -> None:
    networks: set[str] = {cluster.network for cluster in clusters}
    if len(networks) > 1:
        raise MixedNetworksError(message=f"the sites are on more than one network: {sorted(networks)}")


def reject_sites_on_one_cluster(*, clusters: list[ConfiguredCluster]) -> None:
    repeated: list[str] = repeated_values(values=[cluster.api_url for cluster in clusters])
    if repeated:
        raise DuplicateSitesError(message=f"more than one site resolves to the same cluster: {repeated}")


def reject_clusters_that_clash(*, clusters: list[ConfiguredCluster]) -> None:
    for kind, values in (
        ("cluster name", [cluster.name for cluster in clusters]),
        ("host", [cluster_fqdn(api_url=cluster.api_url) for cluster in clusters]),
    ):
        repeated: list[str] = repeated_values(values=values)
        if repeated:
            raise ConfigurationError(
                message=f"different clusters of one Active-Active database share a {kind}: {repeated}"
            )


def repeated_values(*, values: list[str]) -> list[str]:
    return sorted({value for value in values if values.count(value) > 1})
