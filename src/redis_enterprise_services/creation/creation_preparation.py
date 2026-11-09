import logging

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.creation.create_database_request import CreateDatabaseRequest
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.databases.new_database import NewDatabase
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
        cluster: ConfiguredCluster = self._site_cluster_resolver.resolve(
            placement=creation_request.target.single_site()
        )
        filled_database: NewDatabase = self._database_defaults.fill_in(
            cluster=cluster, requested=requested_database
        )
        logger.info(msg=f"creating {filled_database.name} on {cluster.name} is prepared")
        return PreparedCreation(
            cluster=cluster, spec=creation_request.spec.with_database(database=filled_database)
        )
