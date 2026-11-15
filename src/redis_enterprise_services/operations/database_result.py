from typing import ClassVar, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from redis_enterprise_services.config.cluster_inventory import Environment


class DatabasePermissionResult(BaseModel):
    user_uid: int = Field(description="The user's uid on this cluster.", examples=[12])
    user_name: str = Field(description="The user name, as the cluster stored it.", examples=["app"])
    user_password: str = Field(
        description="The user's password: the one the cluster accepted when it created the user "
        "(the cluster never returns passwords).",
        examples=["S3cure-Passw0rd"],
    )
    acl_uid: int = Field(description="The uid of the user's ACL on this cluster.", examples=[9])
    acl_rule: str = Field(
        description="The user's ACL rule, as the cluster stored it: which commands and which key prefix.",
        examples=["+@all ~orders:*"],
    )
    role_uid: int = Field(
        description="The uid of the user's role on this cluster: the role that links the user to its ACL.",
        examples=[4],
    )
    role_name: str = Field(
        description="The role name, as the cluster stored it.", examples=["orders-app-role"]
    )


class DatabaseEndpointResult(BaseModel):
    dns_name: str = Field(
        min_length=1, description="The DNS name clients connect to.", examples=["redis-12000.cluster-a.net-a"]
    )
    port: int = Field(description="The port clients connect to.", examples=[12000])
    addr: list[str] = Field(min_length=1, description="The endpoint's IP addresses.", examples=[["10.0.0.5"]])


class DatabaseAccessResult(BaseModel):
    endpoints: list[DatabaseEndpointResult] = Field(
        min_length=1, description="How clients reach the database on this cluster, as the cluster reports it."
    )


class ClusterDatabaseResult(BaseModel):
    db_uid: int = Field(description="The database uid on this cluster.", examples=[7])
    settings: dict[str, JsonValue] = Field(
        description="Every field of the creation model (spec.database), as the database stored it on this "
        "cluster, read back after it became active.",
        examples=[
            {"name": "orders", "memory_size": 1073741824, "replication": True, "data_persistence": "aof"}
        ],
    )
    permissions: list[DatabasePermissionResult] = Field(
        description="One entry per user: the user, its ACL and its role, which are created and deleted "
        "together."
    )


class DatabaseClusterResult(BaseModel):
    cluster: str = Field(description="The cluster name, as configured.", examples=["cluster-a"])
    cluster_url: str = Field(
        description="The API address of the cluster.",
        examples=["https://cluster-a.net-a:9443"],
    )
    network: str = Field(description="The network of the cluster.", examples=["net-a"])
    site: str = Field(description="The site of the cluster.", examples=["dc1"])
    environment: Environment = Field(description="The environment of the cluster.", examples=["PROD"])
    access: DatabaseAccessResult = Field(description="How clients connect to the database on this cluster.")
    db: ClusterDatabaseResult = Field(description="The database on this cluster, as the cluster stored it.")


class CrdbInstanceResult(BaseModel):
    cluster_url: str = Field(
        description="The API address of the cluster of this instance, the same as the cluster_url of that "
        "cluster in clusters.",
        examples=["https://cluster-a.net-a:9443"],
    )
    instance_id: int = Field(description="The instance id inside the CRDB.", examples=[1])
    compression: int | None = Field(
        ge=0,
        le=6,
        description="The compression level of the sync from this instance (0-6); null only when the "
        "cluster did not report it.",
        examples=[3],
    )


class CrdbResult(BaseModel):
    default_db_config: dict[str, JsonValue] = Field(
        description="The database settings every site shares, as the CRDB stored them: the settings the "
        "service sent, without the secrets, plus the few the cluster fills in itself (port, module_list, "
        "tls_mode, and isSystem on every tag).",
        examples=[
            {"name": "orders", "memory_size": 1073741824, "eviction_policy": "noeviction", "port": 12000}
        ],
    )
    causal_consistency: bool | None = Field(
        description="Whether updates reach every site in the order they depend on each other. The service "
        "always sends it; null only when the cluster did not report it back.",
        examples=[False],
    )
    encryption: bool | None = Field(
        description="Whether the sync between the sites is encrypted. The service always sends it; null "
        "only when the cluster did not report it back.",
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
    instances: list[CrdbInstanceResult] = Field(
        min_length=1, description="One entry per site of the CRDB, in the order the CRDB lists them."
    )


class DatabaseResult(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(json_schema_serialization_defaults_required=True)

    name: str = Field(description="The database name, as the cluster stored it.", examples=["orders"])
    memory_size: int = Field(
        description="The memory limit in bytes, as the cluster stored it.", examples=[1073741824]
    )
    active_active: bool = Field(description="Whether the database is Active-Active.", examples=[False])
    crdb_guid: UUID | None = Field(
        description="The Active-Active database id. Null for a single-site database.", examples=[None]
    )
    crdb: CrdbResult | None = Field(
        default=None,
        description="Only for Active-Active: the settings of the CRDB itself, as it stored them. Null for a "
        "single-site database.",
    )
    clusters: list[DatabaseClusterResult] = Field(
        min_length=1,
        description="One entry per cluster that holds the database: one for a single-site database, one per "
        "site, in the order of the request, for an Active-Active one.",
    )

    @model_validator(mode="after")
    def reject_active_active_fields_that_disagree(self) -> Self:
        has_crdb_guid: bool = self.crdb_guid is not None
        has_crdb: bool = self.crdb is not None
        if has_crdb_guid != self.active_active or has_crdb != self.active_active:
            raise ValueError(
                f"active_active, crdb_guid and crdb must all show the same kind of database, but "
                f"active_active is {self.active_active}, crdb_guid is {'set' if has_crdb_guid else 'null'} "
                f"and crdb is {'set' if has_crdb else 'null'}"
            )
        return self

    @model_validator(mode="after")
    def reject_more_than_one_cluster_for_a_single_site(self) -> Self:
        if not self.active_active and len(self.clusters) != 1:
            raise ValueError(f"a single-site database has exactly one cluster, not {len(self.clusters)}")
        return self
