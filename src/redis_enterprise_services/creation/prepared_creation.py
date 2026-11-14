from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.planning.database_spec import DatabaseSpec


class PreparedCreation(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    clusters: list[ConfiguredCluster] = Field(min_length=1)
    active_active: bool = False
    spec: DatabaseSpec

    @property
    def cluster(self) -> ConfiguredCluster:
        return self.clusters[0]
