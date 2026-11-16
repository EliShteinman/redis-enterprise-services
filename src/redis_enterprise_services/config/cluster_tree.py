from typing import Annotated

from pydantic import AfterValidator, Field

from redis_enterprise_services.config.cluster_flattening import configured_clusters
from redis_enterprise_services.config.cluster_tree_entries import EnvironmentEntries


def checked_tree(tree: EnvironmentEntries) -> EnvironmentEntries:
    configured_clusters(tree=tree)
    return tree


type ClusterTree = Annotated[EnvironmentEntries, Field(min_length=1), AfterValidator(checked_tree)]
