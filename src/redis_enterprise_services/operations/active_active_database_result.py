from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, JsonValue

from redis_enterprise_services.operations.database_result import DatabaseClusterResult


class CrdbResult(BaseModel):
    guid: UUID = Field(
        description="The Active-Active database id.", examples=["d71cefce-4e31-41fd-b654-37cbb2f39a01"]
    )
    causal_consistency: bool = Field(
        description="Whether updates reach every site in the order they depend on each other, as sent and "
        "checked.",
        examples=[False],
    )
    encryption: bool = Field(
        description="Whether the sync between the sites is encrypted, as sent and checked.",
        examples=[False],
    )
    featureset_version: int | None = Field(
        description="The CRDB feature set version, set by Redis; null when the cluster did not report it.",
        examples=[12],
    )
    protocol_version: int | None = Field(
        description="The CRDB sync protocol version, set by Redis; null when the cluster did not report it.",
        examples=[1],
    )
    default_db_config: dict[str, JsonValue] = Field(
        description="The database settings every site shares, as the CRDB stored them: the settings the "
        "service sent, without the secrets, plus the few the cluster fills in itself (port, module_list, "
        "tls_mode, and isSystem on every tag).",
        examples=[
            {"name": "orders", "memory_size": 1073741824, "eviction_policy": "noeviction", "port": 12000}
        ],
    )


class ActiveActiveClusterResult(DatabaseClusterResult):
    instance_id: int = Field(description="The id of this cluster's instance inside the CRDB.", examples=[1])
    compression: int = Field(
        description="The compression level of the sync from this cluster's instance (0-6), as sent and "
        "checked.",
        examples=[3],
    )


class ActiveActiveDatabaseResult(BaseModel):
    kind: Literal["active_active"] = Field(
        description="The kind of the database: active_active, a database on several clusters that sync "
        "with each other. The value is the name of the kind in the service configuration.",
        examples=["active_active"],
    )
    name: str = Field(description="The database name, as the cluster stored it.", examples=["orders"])
    memory_size: int = Field(
        description="The memory limit in bytes, as the cluster stored it.", examples=[1073741824]
    )
    crdb: CrdbResult = Field(description="The settings of the CRDB itself, as it stored them.")
    clusters: list[ActiveActiveClusterResult] = Field(
        min_length=1,
        description="One entry per cluster that holds the database, in the order of the request.",
    )
