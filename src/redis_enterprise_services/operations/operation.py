from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from redis_enterprise_services.operations.database_result import DatabaseResult
from redis_enterprise_services.operations.operation_status import CLEANLY_ENDED_STATUSES, OperationStatus
from redis_enterprise_services.operations.public_error import PublicError
from redis_enterprise_services.operations.remaining_resource import RemainingResource

STATUSES_WITHOUT_ERROR: frozenset[OperationStatus] = frozenset(
    {OperationStatus.RUNNING, OperationStatus.SUCCEEDED}
)


class Operation(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(json_schema_serialization_defaults_required=True)

    trace_id: str = Field(
        description="The trace ID of the request that started the operation.",
        examples=["4bf92f3577b34da6a3ce929d0e0e4736"],
    )
    status: OperationStatus = Field(
        default=OperationStatus.RUNNING,
        description="running: still running. succeeded: done. rejected: refused before anything changed. "
        "rolled_back: failed, and everything was undone. requires_manual_intervention: failed, "
        "and not everything was undone (see not_rolled_back, which is missing after a crash; then the "
        "saga record is the source), or the pod stopped after the run succeeded and before it saved the "
        "operation (the database exists, but database is null).",
        examples=["succeeded"],
    )
    database: DatabaseResult | None = Field(
        default=None, description="The database as it is now, when the operation succeeded. Otherwise null."
    )
    error: PublicError | None = Field(
        default=None,
        exclude_if=lambda error: error is None,
        description="Why the operation did not succeed. Present for every status except running and "
        "succeeded.",
    )
    not_rolled_back: list[RemainingResource] | None = Field(
        default=None,
        exclude_if=lambda not_rolled_back: not_rolled_back is None,
        description="What stayed on the clusters after a failure. Empty when everything was undone.",
    )

    @model_validator(mode="after")
    def reject_an_error_that_does_not_fit_the_status(self) -> Self:
        if (self.error is None) != (self.status in STATUSES_WITHOUT_ERROR):
            raise ValueError(f"an operation {self.status.value} has an error exactly when it did not succeed")
        return self

    def has_ended_cleanly(self) -> bool:
        return self.status in CLEANLY_ENDED_STATUSES

    @classmethod
    def rejected(cls, *, trace_id: str, error: PublicError) -> Self:
        return cls(trace_id=trace_id, status=OperationStatus.REJECTED, error=error)

    @classmethod
    def requires_manual_intervention(cls, *, trace_id: str, error: PublicError) -> Self:
        return cls(trace_id=trace_id, status=OperationStatus.REQUIRES_MANUAL_INTERVENTION, error=error)
