import logging
from collections.abc import Sequence

from pydantic import BaseModel

from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.creation.active_active_cluster_rules import (
    reject_clusters_that_cannot_share_a_crdb,
)
from redis_enterprise_services.creation.create_crdb_request import CreateCrdbRequest
from redis_enterprise_services.creation.prepared_active_active_creation import PreparedActiveActiveCreation
from redis_enterprise_services.databases.new_database import PERSISTENCE_MODE_BY_FIELD, NewDatabase
from redis_enterprise_services.exceptions.configuration import ConfigurationError
from redis_enterprise_services.planning.naming.name_validator import NameValidator
from redis_enterprise_services.planning.naming.user_names_validator import UserNamesValidator
from redis_enterprise_services.planning.placement.site_cluster_resolver import SiteClusterResolver
from redis_enterprise_services.planning.spec.crdb_spec import CrdbSpec
from redis_enterprise_services.planning.spec.database_defaults import DATA_PERSISTENCE_FIELD, DatabaseDefaults

logger: logging.Logger = logging.getLogger(name=__name__)


class ActiveActivePreparation:
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

    def prepare(self, *, creation_request: CreateCrdbRequest) -> PreparedActiveActiveCreation:
        self._ensure_valid_names_on_every_site(creation_request=creation_request)
        clusters: list[ConfiguredCluster] = [
            self._site_cluster_resolver.resolve(placement=site) for site in creation_request.target.sites
        ]
        reject_clusters_that_cannot_share_a_crdb(clusters=clusters)
        filled_database: NewDatabase = self._same_database_on_every_site(
            clusters=clusters, requested=creation_request.spec.database
        )
        self._ensure_same_crdb_settings_on_every_site(clusters=clusters, requested=creation_request.spec.crdb)
        logger.info(
            msg=f"creating Active-Active {filled_database.name} on "
            f"{[cluster.fqdn for cluster in clusters]} is prepared"
        )
        return PreparedActiveActiveCreation(
            clusters=clusters, spec=creation_request.spec.with_database(database=filled_database)
        )

    def _ensure_valid_names_on_every_site(self, *, creation_request: CreateCrdbRequest) -> None:
        for context in creation_request.target.naming_contexts():
            self._name_validator.ensure_valid(name=creation_request.spec.database.name, context=context)
            self._user_names_validator.ensure_valid(spec=creation_request.spec, context=context)

    def _same_database_on_every_site(
        self, *, clusters: list[ConfiguredCluster], requested: NewDatabase
    ) -> NewDatabase:
        filled: list[NewDatabase] = [
            self._database_defaults.fill_in(cluster=cluster, requested=requested, active_active=True)
            for cluster in clusters
        ]
        differing: list[str] = database_differences_to_report(differing=differing_fields(values=filled))
        if differing:
            raise ConfigurationError(
                message=f"the database defaults give {differing} different values on "
                f"{[cluster.fqdn for cluster in clusters]}"
            )
        return filled[0]

    def _ensure_same_crdb_settings_on_every_site(
        self, *, clusters: list[ConfiguredCluster], requested: CrdbSpec | None
    ) -> None:
        differing: list[str] = differing_fields(
            values=[
                self._database_defaults.crdb_settings(cluster=cluster, requested=requested)
                for cluster in clusters
            ],
        )
        if differing:
            raise ConfigurationError(
                message=f"the CRDB defaults give {differing} different values on "
                f"{[cluster.fqdn for cluster in clusters]}"
            )


def differing_fields(*, values: Sequence[BaseModel]) -> list[str]:
    return sorted(
        name
        for name in type(values[0]).model_fields
        if any(getattr(value, name) != getattr(values[0], name) for value in values)
    )


def database_differences_to_report(*, differing: list[str]) -> list[str]:
    if DATA_PERSISTENCE_FIELD in differing:
        return [name for name in differing if name not in PERSISTENCE_MODE_BY_FIELD]
    return differing
