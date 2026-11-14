from typing import Literal

from pydantic import BaseModel, Field

from redis_enterprise_services.operations.is_none import is_none

type RemainingResourceType = Literal["crdb", "database", "acl", "role", "user", "permissions"]


class RemainingResource(BaseModel):
    cluster_url: str = Field(
        description="The cluster the resource is on.", examples=["https://cluster-a.net-a:9443"]
    )
    resource_type: RemainingResourceType = Field(
        description="crdb is the Active-Active database itself, with its local databases on every site. "
        "permissions are the role-to-ACL links of the database.",
        examples=["acl"],
    )
    name: str = Field(
        description="The resource name. For permissions: the database name.", examples=["orders-app-acl"]
    )
    uid: int | None = Field(
        description="The resource uid on the cluster, or null when it is unknown whether it was created. "
        "For permissions: the database uid.",
        examples=[11],
    )
    crdb_guid: str | None = Field(
        default=None,
        exclude_if=is_none,
        description="Only for crdb: the CRDB guid, or missing when it is unknown whether it was created.",
        examples=["d71cefce-4e31-41fd-b654-37cbb2f39a01"],
    )
    last_error: str | None = Field(
        description="The last error of the resource, as '<code>: <message>': of its undo when the undo "
        "failed, otherwise of its step. The code is one of the error.code values. Null when there was none.",
        examples=["cluster_unavailable: relay is down"],
    )
