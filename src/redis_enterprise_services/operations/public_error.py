from pydantic import BaseModel, Field


class PublicError(BaseModel):
    code: str = Field(
        description="What kind of failure. At once: validation_error (the request does not match), "
        "invalid_name (a name breaks the naming rules), "
        "no_matching_cluster (no configured cluster for the target), "
        "not_found (unknown path), operation_not_found (unknown or expired trace id), "
        "method_not_allowed (the path does not take this method), "
        "configuration_error (the service configuration cannot serve the request), "
        "internal_error (a bug in the service). "
        "In the status: name_taken, "
        "resources_locked (another operation holds the database or one of its users), "
        "cluster_request_failed (the cluster refused or failed a request), "
        "cluster_unavailable (the cluster or the edge service cannot be reached), cluster_timeout "
        "(the cluster did not finish in time), internal_error.",
        examples=["cluster_request_failed"],
    )
    message: str = Field(
        description="What went wrong, for people; not for parsing.",
        examples=["cluster answered 406: Cannot allocate nodes for shards"],
    )
    cluster_url: str | None = Field(
        default=None,
        exclude_if=lambda cluster_url: cluster_url is None,
        description="The cluster the error came from. Only for errors from a cluster.",
        examples=["https://cluster-a.net-a:9443"],
    )
    cluster_error_code: str | None = Field(
        default=None,
        exclude_if=lambda cluster_error_code: cluster_error_code is None,
        description="The cluster's own error code. Only for errors from a cluster.",
        examples=["insufficient_resources"],
    )
