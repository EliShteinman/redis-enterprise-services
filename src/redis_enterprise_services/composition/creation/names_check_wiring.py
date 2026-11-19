from redis_enterprise_services.cluster.cluster_target_resolver import ClusterTargetResolver
from redis_enterprise_services.composition.cluster.cluster_repositories import ClusterRepositories
from redis_enterprise_services.planning.availability.chosen_cluster_scope import ChosenClusterScope
from redis_enterprise_services.planning.availability.creation_names_check import CreationNamesCheck
from redis_enterprise_services.planning.availability.creation_naming import CreationNaming
from redis_enterprise_services.planning.availability.lookups.combined_name_lookup import CombinedNameLookup
from redis_enterprise_services.planning.availability.lookups.crdb_name_lookup import CrdbNameLookup
from redis_enterprise_services.planning.availability.lookups.listed_name_lookup import ListedNameLookup
from redis_enterprise_services.planning.availability.lookups.name_lookups_by_kind import NameLookupsByKind
from redis_enterprise_services.planning.availability.name_availability import NameAvailability
from redis_enterprise_services.planning.planned.user_resource_naming import UserResourceNaming


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
