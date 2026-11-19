from typing import Protocol

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.models import ClusterObject


class ResourceNameLister(Protocol):
    def list_objects(self, *, target: ClusterTarget) -> list[ClusterObject]: ...
