from typing import Protocol

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.resources.models import NamedResource


class ResourceNameLister(Protocol):
    def list_uids_and_names(self, *, target: ClusterTarget) -> list[NamedResource]: ...
