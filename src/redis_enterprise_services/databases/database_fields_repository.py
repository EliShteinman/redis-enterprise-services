from typing import Protocol

from pydantic import JsonValue

from redis_enterprise_services.cluster.models import ClusterTarget
from redis_enterprise_services.databases.models import DatabaseFieldsSnapshot


class DatabaseFieldsReader(Protocol):
    def read_fields(
        self, *, target: ClusterTarget, uid: int, field_names: list[str]
    ) -> DatabaseFieldsSnapshot: ...


class DatabaseFieldsRepository(DatabaseFieldsReader, Protocol):
    def update_fields_if_state_unchanged(
        self, *, target: ClusterTarget, uid: int, values: dict[str, JsonValue], cluster_state_id: int
    ) -> None: ...
