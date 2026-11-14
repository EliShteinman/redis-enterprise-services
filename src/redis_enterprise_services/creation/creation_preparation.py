import logging

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.creation.create_database_request import CreateDatabaseRequest
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.exceptions.planning import MixedNetworksError
from redis_enterprise_services.planning.database_defaults import DatabaseDefaults
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
        filled_database: NewDatabase = self._same_database_on_every_site(
            clusters=clusters, requested=requested_database
        )
        logger.info(msg=f"creating {filled_database.name} on {[c.name for c in clusters]} is prepared")
        return PreparedCreation(
            clusters=clusters,
            active_active=creation_request.target.active_active,
            spec=creation_request.spec.with_database(database=filled_database),
        )

    def _same_database_on_every_site(
        self, *, clusters: list[ConfiguredCluster], requested: NewDatabase
    ) -> NewDatabase:
        filled: list[NewDatabase] = [
            self._database_defaults.fill_in(cluster=cluster, requested=requested) for cluster in clusters
        ]
        if any(database != filled[0] for database in filled):
            raise ConfigurationError(
                message=f"the database defaults give different settings on {[c.name for c in clusters]}"
            )
        return filled[0]


def reject_mixed_networks(*, clusters: list[ConfiguredCluster]) -> None:
    networks: set[str] = {cluster.network for cluster in clusters}
    if len(networks) > 1:
        raise MixedNetworksError(message=f"the sites are on more than one network: {sorted(networks)}")
