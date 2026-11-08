from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from redis_enterprise_services.config.cluster_inventory import ClusterEntry
from redis_enterprise_services.planning.database_creation_request import DatabaseCreationRequest


class PreparedCreation(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    cluster: ClusterEntry
    request: DatabaseCreationRequest
