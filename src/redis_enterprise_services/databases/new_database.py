from typing import Literal

from pydantic import BaseModel, Field, PositiveInt

from redis_enterprise_services.resources.spec import NamedSpec


class ShardKeyRegex(BaseModel):
    regex: str


class SnapshotPolicy(BaseModel):
    secs: PositiveInt
    writes: PositiveInt


class NewDatabase(NamedSpec):
    memory_size: PositiveInt
    version: str | None = None
    replication: bool | None = None
    sharding: bool | None = None
    shards_count: int | None = Field(default=None, ge=1, le=512)
    shard_key_regex: list[ShardKeyRegex] | None = None
    data_persistence: Literal["disabled", "snapshot", "aof"] | None = None
    aof_policy: Literal["appendfsync-every-sec", "appendfsync-always"] | None = None
    snapshot_policy: list[SnapshotPolicy] | None = None
    eviction_policy: str | None = None
    shards_placement: Literal["dense", "sparse"] | None = None
    proxy_policy: Literal["single", "all-master-shards", "all-nodes"] | None = None
    slave_ha: bool | None = None
