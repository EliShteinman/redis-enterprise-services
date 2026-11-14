from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from redis_enterprise_services.config.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.planning.database_spec import DatabaseSpec


class PreparedCreation(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    clusters: list[ConfiguredCluster] = Field(min_length=1)
    active_active: bool
    spec: DatabaseSpec

    @property
    def cluster(self) -> ConfiguredCluster:
        return self.clusters[0]

    @model_validator(mode="after")
    def reject_more_than_one_cluster_for_a_single_site(self) -> Self:
        if not self.active_active and len(self.clusters) != 1:
            raise ValueError(f"a single-site creation has exactly one cluster, not {len(self.clusters)}")
        return self
