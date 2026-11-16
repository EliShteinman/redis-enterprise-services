from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from redis_enterprise_services.config.clusters.cluster_inventory import ConfiguredCluster
from redis_enterprise_services.planning.spec.active_active_spec import ActiveActiveSpec


class PreparedActiveActiveCreation(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    clusters: list[ConfiguredCluster] = Field(min_length=1)
    spec: ActiveActiveSpec
