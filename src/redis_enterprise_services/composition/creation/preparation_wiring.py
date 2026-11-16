from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.config.defaults.database_defaults_settings import DatabaseDefaultsSettings
from redis_enterprise_services.config.defaults.naming_settings import NamingSettings, RedisNameRulesSettings
from redis_enterprise_services.planning.naming.configured_name_rules import configured_name_rules
from redis_enterprise_services.planning.naming.name_validator import NameValidator
from redis_enterprise_services.planning.naming.user_names_validator import UserNamesValidator
from redis_enterprise_services.planning.placement.cluster_directory import ClusterDirectory
from redis_enterprise_services.planning.placement.single_candidate_chooser import SingleCandidateChooser
from redis_enterprise_services.planning.placement.site_cluster_resolver import SiteClusterResolver
from redis_enterprise_services.planning.planned.user_resource_naming import UserResourceNaming
from redis_enterprise_services.planning.spec.database_defaults import DatabaseDefaults
from redis_enterprise_services.planning.spec.database_defaults_validation import (
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
