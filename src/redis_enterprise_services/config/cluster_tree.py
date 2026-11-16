from typing import Annotated

from pydantic import Field

from redis_enterprise_services.config.cluster_tree_entries import EnvironmentEntries

type ClusterTree = Annotated[EnvironmentEntries, Field(min_length=1)]
