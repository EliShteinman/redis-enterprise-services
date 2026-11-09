from typing import ClassVar, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator

from redis_enterprise_services.resources.named_spec import NamedSpec

type DataPersistence = Literal["disabled", "snapshot", "aof"]

PERSISTENCE_MODE_BY_FIELD: dict[str, DataPersistence] = {"aof_policy": "aof", "snapshot_policy": "snapshot"}

UNSET_MEANS_DEFAULT_DESCRIPTION: str = (
    " When omitted or null, the service's configured default for the target applies,"
    " or else Redis's own default."
)


class ShardKeyRegex(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    regex: str = Field(
        description="A regex whose named group `tag` is the part of the key that picks the shard.",
        examples=[".*\\{(?<tag>.*)\\}.*"],
    )


class SnapshotRule(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    secs: PositiveInt = Field(description="Seconds since the last snapshot.", examples=[3600])
    writes: PositiveInt = Field(description="Keys changed since the last snapshot.", examples=[1])


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


class DatabaseOptions(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    version: str | None = Field(
        default=None,
        description="The Redis version of the database." + UNSET_MEANS_DEFAULT_DESCRIPTION,
        examples=["8.4"],
    )
    replication: bool | None = Field(
        default=None,
        description="Keep a replica of every shard on another node." + UNSET_MEANS_DEFAULT_DESCRIPTION,
        examples=[True],
    )
    sharding: bool | None = Field(
        default=None,
        description="Split the data across several shards." + UNSET_MEANS_DEFAULT_DESCRIPTION,
        examples=[False],
    )
    shards_count: int | None = Field(
        default=None,
        ge=1,
        le=512,
        description="The number of primary shards." + UNSET_MEANS_DEFAULT_DESCRIPTION,
        examples=[1],
    )
    shard_key_regex: list[ShardKeyRegex] | None = Field(
        default=None,
        description="Only with sharding: how a key picks its shard, first match wins."
        + UNSET_MEANS_DEFAULT_DESCRIPTION,
        examples=[[{"regex": ".*\\{(?<tag>.*)\\}.*"}, {"regex": "(?<tag>.*)"}]],
    )
    data_persistence: DataPersistence | None = Field(
        default=None,
        description="How the data survives a restart: not at all, periodic snapshots, "
        "or an append-only file of every write." + UNSET_MEANS_DEFAULT_DESCRIPTION,
        examples=["aof"],
    )
    aof_policy: Literal["appendfsync-every-sec", "appendfsync-always"] | None = Field(
        default=None,
        description="Only with aof, sent together with data_persistence aof: write to disk every second, "
        "or on every write." + UNSET_MEANS_DEFAULT_DESCRIPTION,
        examples=["appendfsync-every-sec"],
    )
    snapshot_policy: list[SnapshotRule] | None = Field(
        default=None,
        description="Only with snapshot, sent together with data_persistence snapshot: take a snapshot "
        "when any rule matches." + UNSET_MEANS_DEFAULT_DESCRIPTION,
        examples=[[{"secs": 3600, "writes": 1}]],
    )
    eviction_policy: EvictionPolicy | None = Field(
        default=None,
        description="Which keys are removed when the database is full; noeviction refuses writes instead."
        + UNSET_MEANS_DEFAULT_DESCRIPTION,
        examples=["volatile-lru"],
    )
    shards_placement: Literal["dense", "sparse"] | None = Field(
        default=None,
        description="dense: shards on as few nodes as possible. sparse: spread across the nodes."
        + UNSET_MEANS_DEFAULT_DESCRIPTION,
        examples=["dense"],
    )
    proxy_policy: Literal["single", "all-master-shards", "all-nodes"] | None = Field(
        default=None,
        description="Which nodes serve the database endpoint." + UNSET_MEANS_DEFAULT_DESCRIPTION,
        examples=["all-master-shards"],
    )
    slave_ha: bool | None = Field(
        default=None,
        description="Move a replica to a healthy node when its node fails." + UNSET_MEANS_DEFAULT_DESCRIPTION,
        examples=[True],
    )

    @model_validator(mode="after")
    def reject_persistence_settings_of_another_mode(self) -> Self:
        for field, mode in PERSISTENCE_MODE_BY_FIELD.items():
            if getattr(self, field) is not None and self.data_persistence != mode:
                raise ValueError(f"{field} is sent only together with data_persistence {mode}")
        return self


class NewDatabase(NamedSpec, DatabaseOptions):
    name: str = Field(
        description="The database name. Letters, digits and '-' (not first or last), "
        "up to the configured length. A name that breaks these rules is refused at once with invalid_name. "
        "A name already taken on the cluster ends the operation as rejected with name_taken.",
        examples=["orders"],
    )
    memory_size: PositiveInt = Field(
        description="The memory limit of the database, in bytes.", examples=[1073741824]
    )
