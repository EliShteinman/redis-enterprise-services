from typing import Self

from pydantic import BaseModel, Field

from redis_enterprise_services.config.error_kind import ErrorKind
from redis_enterprise_services.config.public_error_code import PublicErrorCode
from redis_enterprise_services.operations.code_meanings import code_meanings_description
from redis_enterprise_services.operations.is_none import is_none

PUBLIC_ERROR_CODE_MEANINGS: dict[PublicErrorCode, str] = {
    "name_taken": "a name is taken on the cluster",
    "resources_locked": "another operation holds the database or one of its users",
    "invalid_name": "a name breaks the naming rules",
    "no_matching_cluster": "no configured cluster for the target",
    "cluster_request_failed": "the cluster refused or failed a request",
    "cluster_unavailable": "the cluster or the edge service cannot be reached",
    "cluster_timeout": "the cluster did not finish in time",
    "configuration_error": "the service configuration cannot serve the request",
    "internal_error": "an unexpected failure inside the service, such as a bug or the service stopping",
}


PUBLIC_ERROR_CODE_DESCRIPTION: str = code_meanings_description(meanings=PUBLIC_ERROR_CODE_MEANINGS)

NEEDS_INVESTIGATION: ErrorKind = "needs_investigation"
ERROR_KIND_MEANINGS: dict[ErrorKind, str] = {
    "customer_fixable": "the customer can understand and fix it alone",
    "known_failure": "support knows the cause from the code",
    NEEDS_INVESTIGATION: "someone has to follow the trace through the chain",
}
ERROR_KIND_DESCRIPTION: str = code_meanings_description(meanings=ERROR_KIND_MEANINGS)


class PublicError(BaseModel):
    code: PublicErrorCode = Field(
        description="What kind of failure: " + PUBLIC_ERROR_CODE_DESCRIPTION + ".",
        examples=["cluster_request_failed"],
    )
    kind: ErrorKind = Field(
        description="What to do with it: " + ERROR_KIND_DESCRIPTION + ". Every requires_manual_intervention "
        "is needs_investigation. A kind added later should be read as needs_investigation.",
        examples=["known_failure"],
    )
    message: str = Field(
        description="What went wrong, for people; not for parsing.",
        examples=["the request was refused with status 406 (insufficient_resources)"],
    )
    cluster_url: str | None = Field(
        default=None,
        exclude_if=is_none,
        description="The cluster the error came from. Only for errors from a cluster.",
        examples=["https://cluster-a.net-a:9443"],
    )
    cluster_error_code: str | None = Field(
        default=None,
        exclude_if=is_none,
        description="The cluster's own error code. Only for errors from a cluster.",
        examples=["insufficient_resources"],
    )

    def needing_investigation(self) -> Self:
        return self.model_copy(update={"kind": NEEDS_INVESTIGATION})
