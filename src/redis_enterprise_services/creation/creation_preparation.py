import logging

from redis_enterprise_services.config.clusters_settings import ClusterEntry
from redis_enterprise_services.creation.creation_request import CreationRequest
from redis_enterprise_services.creation.prepared_creation import PreparedCreation
from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.planning.cluster_resolver import ClusterResolver
from redis_enterprise_services.planning.database_defaults import DatabaseDefaults
from redis_enterprise_services.planning.naming.name_validator import NameValidator
from redis_enterprise_services.planning.naming.naming_context import NamingContext

logger: logging.Logger = logging.getLogger(name=__name__)


class CreationPreparation:
    def __init__(
        self, *, validator: NameValidator, resolver: ClusterResolver, defaults: DatabaseDefaults
    ) -> None:
        self._validator: NameValidator = validator
        self._resolver: ClusterResolver = resolver
        self._defaults: DatabaseDefaults = defaults

    def prepare(self, *, request: CreationRequest) -> PreparedCreation:
        requested: NewDatabase = request.body.database
        self._validator.ensure_valid(
            name=requested.name,
            context=NamingContext(active_active=request.target.active_active, sites=request.target.sites),
        )
        cluster: ClusterEntry = self._resolver.resolve(target=request.target.sites[0])
        database: NewDatabase = self._defaults.complete(cluster=cluster, requested=requested)
        logger.info(msg=f"creating {database.name} on {cluster.name} is prepared")
        return PreparedCreation(
            cluster=cluster, request=request.body.model_copy(update={"database": database})
        )
