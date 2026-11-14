from typing import Protocol

from pydantic import JsonValue

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.crdbs.models import Crdb
from redis_enterprise_services.databases.new_database import NewDatabase


class CrdbRepository(Protocol):
    def start_creation(
        self, *, coordinator: ClusterTarget, members: list[ClusterTarget], database: NewDatabase, task_id: str
    ) -> None: ...

    def read(self, *, target: ClusterTarget, guid: str) -> Crdb: ...

    def list_crdbs(self, *, target: ClusterTarget) -> list[Crdb]: ...

    def list_crdb_names(self, *, target: ClusterTarget) -> set[str]: ...

    def start_update(
        self, *, target: ClusterTarget, guid: str, changes: dict[str, JsonValue], task_id: str
    ) -> None: ...

    def start_instances_update(
        self,
        *,
        target: ClusterTarget,
        guid: str,
        values_by_instance: dict[int, dict[str, JsonValue]],
        task_id: str,
    ) -> None: ...

    def start_deletion(self, *, target: ClusterTarget, guid: str, task_id: str) -> None: ...
