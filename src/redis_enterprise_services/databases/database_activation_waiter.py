from typing import Protocol

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.databases.models import DatabaseFieldsSnapshot


class DatabaseActivationWaiter(Protocol):
    def wait_until_active(self, *, target: ClusterTarget, uid: int) -> DatabaseFieldsSnapshot: ...
