from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from redis_enterprise_services.operations.is_none import is_none

type RemainingResourceType = Literal["crdb", "database", "acl", "role", "user", "permissions"]


CRDB_GUID_RESOURCE_TYPES: frozenset[RemainingResourceType] = frozenset({"crdb", "permissions"})


class RemainingResource(BaseModel):
    cluster_url: str = Field(
        description="The cluster the resource is on.", examples=["https://cluster-a.net-a:9443"]
    )
    resource_type: RemainingResourceType = Field(
        description="crdb is the Active-Active database itself, with its local databases on every site. "
        "permissions are the role-to-ACL links of the database.",
        examples=["crdb"],
    )
    name: str = Field(
        description="The resource name. For permissions and crdb: the database name.",
        examples=["orders"],
    )
    uid: int | None = Field(
        description="The resource uid on the cluster, or null when it is unknown whether it was created. "
        "For permissions: the database uid. Always null for crdb and for Active-Active permissions, which "
        "crdb_guid identifies instead.",
        examples=[None],
    )
    crdb_guid: UUID | None = Field(
        default=None,
        exclude_if=is_none,
        description="Only for crdb and Active-Active permissions: the CRDB guid. For crdb, missing when it "
        "is unknown whether the CRDB was created. A crdb item and an Active-Active permissions item, which "
        "covers every site, are reported on the coordinator, the first site.",
        examples=["d71cefce-4e31-41fd-b654-37cbb2f39a01"],
    )
    last_error: str | None = Field(
        description="The last error of the resource, as '<code>: <message>': of its undo when the undo "
        "failed, otherwise of its step. The code is one of the error.code values. Null when there was none.",
        examples=["cluster_unavailable: relay is down"],
    )

    @model_validator(mode="after")
    def reject_a_guid_on_a_resource_without_a_crdb(self) -> Self:
        if self.crdb_guid is not None and self.resource_type not in CRDB_GUID_RESOURCE_TYPES:
            raise ValueError(f"a {self.resource_type} resource cannot carry a crdb_guid")
        return self

    @model_validator(mode="after")
    def reject_a_uid_on_a_resource_the_crdb_identifies(self) -> Self:
        if self.uid is not None and (self.resource_type == "crdb" or self.crdb_guid is not None):
            raise ValueError(f"a {self.resource_type} resource identified by its CRDB cannot carry a uid")
        return self
