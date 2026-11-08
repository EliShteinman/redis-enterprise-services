from typing import Protocol

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.models import NamedResource


class NamedResourceLister(Protocol):
    def list_named(self, *, target: ClusterTarget) -> list[NamedResource]: ...
