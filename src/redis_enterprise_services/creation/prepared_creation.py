from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from redis_enterprise_services.config.clusters_settings import ClusterEntry
from redis_enterprise_services.planning.database_request import DatabaseRequest


class PreparedCreation(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    cluster: ClusterEntry
    request: DatabaseRequest
