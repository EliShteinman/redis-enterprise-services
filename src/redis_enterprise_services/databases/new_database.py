from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from redis_enterprise_services.resources.spec import NamedSpec


class ShardKeyRegex(BaseModel):
    regex: str


class SnapshotPolicy(BaseModel):
    secs: PositiveInt
    writes: PositiveInt


type EvictionPolicy = Literal[
    "volatile-lru",
    "volatile-ttl",
    "volatile-random",
    "allkeys-lru",
    "allkeys-random",
    "noeviction",
    "volatile-lfu",
    "allkeys-lfu",
    "allkeys-lrm",
    "volatile-lrm",
]


class NewDatabase(NamedSpec):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    memory_size: PositiveInt
    version: str | None = None
    replication: bool | None = None
    sharding: bool | None = None
    shards_count: int | None = Field(default=None, ge=1, le=512)
    shard_key_regex: list[ShardKeyRegex] | None = None
    data_persistence: Literal["disabled", "snapshot", "aof"] | None = None
    aof_policy: Literal["appendfsync-every-sec", "appendfsync-always"] | None = None
    snapshot_policy: list[SnapshotPolicy] | None = None
    eviction_policy: EvictionPolicy | None = None
    shards_placement: Literal["dense", "sparse"] | None = None
    proxy_policy: Literal["single", "all-master-shards", "all-nodes"] | None = None
    slave_ha: bool | None = None
