from redis_enterprise_services.cluster.cluster_target_resolver import ClusterTargetResolver
from redis_enterprise_services.composition.cluster.cluster_repositories import ClusterRepositories
from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.defaults.database_defaults_settings import DatabaseDefaultsSettings
from redis_enterprise_services.config.defaults.naming_settings import NamingSettings, RedisNameRulesSettings
from redis_enterprise_services.planning.availability.chosen_cluster_scope import ChosenClusterScope
from redis_enterprise_services.planning.availability.creation_names_check import CreationNamesCheck
from redis_enterprise_services.planning.availability.creation_naming import CreationNaming
from redis_enterprise_services.planning.availability.lookups.combined_name_lookup import CombinedNameLookup
from redis_enterprise_services.planning.availability.lookups.crdb_name_lookup import CrdbNameLookup
from redis_enterprise_services.planning.availability.lookups.listed_name_lookup import ListedNameLookup
from redis_enterprise_services.planning.availability.lookups.name_lookups_by_kind import NameLookupsByKind
from redis_enterprise_services.planning.availability.name_availability import NameAvailability
from redis_enterprise_services.planning.naming.configured_name_rules import configured_name_rules
from redis_enterprise_services.planning.naming.name_validator import NameValidator
from redis_enterprise_services.planning.naming.user_names_validator import UserNamesValidator
from redis_enterprise_services.planning.placement.cluster_directory import ClusterDirectory
from redis_enterprise_services.planning.placement.single_candidate_chooser import SingleCandidateChooser
from redis_enterprise_services.planning.placement.site_cluster_resolver import SiteClusterResolver
from redis_enterprise_services.planning.planned.user_resource_naming import UserResourceNaming
from redis_enterprise_services.planning.spec.database_defaults import (
    DatabaseDefaults,
    reject_invalid_defaults_on_any_cluster,
)


def checked_database_defaults(
    *, settings: DatabaseDefaultsSettings, clusters: list[ConfiguredCluster]
) -> DatabaseDefaults:
    reject_invalid_defaults_on_any_cluster(settings=settings, clusters=clusters)
    return DatabaseDefaults(settings=settings)


def build_database_name_validator(*, naming: NamingSettings) -> NameValidator:
    return NameValidator(
        rules=[
            *configured_name_rules(settings=naming.redis.database),
            *configured_name_rules(settings=naming.database),
        ]
    )


def build_user_names_validator(
    *, redis_names: RedisNameRulesSettings, resource_naming: UserResourceNaming
) -> UserNamesValidator:
    return UserNamesValidator(
        user_name_validator=NameValidator(rules=configured_name_rules(settings=redis_names.user)),
        acl_and_role_name_validator=NameValidator(
            rules=configured_name_rules(settings=redis_names.acl_and_role)
        ),
        resource_naming=resource_naming,
    )


def build_site_cluster_resolver(*, clusters: list[ConfiguredCluster]) -> SiteClusterResolver:
    return SiteClusterResolver(
        directory=ClusterDirectory(clusters=clusters), chooser=SingleCandidateChooser()
    )


def build_names_check(
    *,
    repositories: ClusterRepositories,
    target_resolver: ClusterTargetResolver,
    resource_naming: UserResourceNaming,
) -> CreationNamesCheck:
    return CreationNamesCheck(
        name_check_scope=ChosenClusterScope(),
        name_availability=NameAvailability(
            lookups=NameLookupsByKind(
                database=CombinedNameLookup(
                    lookups=[
                        ListedNameLookup(lister=repositories.database),
                        CrdbNameLookup(repository=repositories.crdb),
                    ]
                ),
                acl=ListedNameLookup(lister=repositories.acl),
                role=ListedNameLookup(lister=repositories.role),
                user=ListedNameLookup(lister=repositories.user),
            ),
            target_resolver=target_resolver,
        ),
        creation_naming=CreationNaming(resource_naming=resource_naming),
    )
