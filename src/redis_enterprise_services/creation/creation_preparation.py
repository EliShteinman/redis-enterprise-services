import logging

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.creation.creation_request import CreationRequest
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.planning.database_defaults import DatabaseDefaults
from redis_enterprise_services.planning.naming.name_validator import NameValidator
from redis_enterprise_services.planning.naming.naming_context import NamingContext
from redis_enterprise_services.planning.site_cluster_resolver import SiteClusterResolver

logger: logging.Logger = logging.getLogger(name=__name__)


class CreationPreparation:
    def __init__(
        self,
        *,
        name_validator: NameValidator,
        site_cluster_resolver: SiteClusterResolver,
        database_defaults: DatabaseDefaults,
    ) -> None:
        self._name_validator: NameValidator = name_validator
        self._site_cluster_resolver: SiteClusterResolver = site_cluster_resolver
        self._database_defaults: DatabaseDefaults = database_defaults

    def prepare(self, *, request: CreationRequest) -> PreparedCreation:
        requested_database: NewDatabase = request.spec.database
        self._name_validator.ensure_valid(
            name=requested_database.name,
            context=NamingContext(active_active=request.target.active_active, sites=request.target.sites),
        )
        cluster: ConfiguredCluster = self._site_cluster_resolver.resolve(placement=request.target.sites[0])
        filled_database: NewDatabase = self._database_defaults.fill_in(
            cluster=cluster, requested=requested_database
        )
        logger.info(msg=f"creating {filled_database.name} on {cluster.name} is prepared")
        return PreparedCreation(
            cluster=cluster, spec=request.spec.model_copy(update={"database": filled_database})
        )
