from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.planning.spec.database_spec import DatabaseSpec


class PreparedCreation(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    cluster: ConfiguredCluster
    spec: DatabaseSpec
