from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from redis_enterprise_services.operations.database_result import DatabaseResult
from redis_enterprise_services.operations.is_none import is_none
from redis_enterprise_services.operations.operation_status import (
    CLEANLY_ENDED_STATUSES,
    STATUSES_WITH_REMAINING_RESOURCES,
    STATUSES_WITHOUT_ERROR,
    OperationStatus,
)
from redis_enterprise_services.operations.public_error import PublicError
from redis_enterprise_services.operations.remaining_resource import RemainingResource


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
        "and not everything was undone (see not_rolled_back, which is missing when the service stopped "
        "mid-run: then an operator checks what was left), or the pod stopped after the run succeeded "
        "and before it saved the "
        "operation (the database exists, but database is null).",
        examples=["succeeded"],
    )
    database: DatabaseResult | None = Field(
        default=None,
        description="The database as the cluster reported it when the operation ended, when it succeeded. "
        "Otherwise null.",
    )
    error: PublicError | None = Field(
        default=None,
        exclude_if=is_none,
        description="Why the operation did not succeed. Present for every status except running and "
        "succeeded.",
    )
    not_rolled_back: list[RemainingResource] | None = Field(
        default=None,
        exclude_if=is_none,
        description="What stayed on the clusters when the operation did not succeed. Empty when everything "
        "was undone.",
    )

    @model_validator(mode="after")
    def reject_fields_that_do_not_fit_the_status(self) -> Self:
        problem: str | None = status_fields_problem(operation=self)
        if problem is not None:
            raise ValueError(f"an operation that is {self.status.value} {problem}")
        return self

    def has_ended_cleanly(self) -> bool:
        return self.status in CLEANLY_ENDED_STATUSES

    @classmethod
    def rejected(cls, *, trace_id: str, error: PublicError) -> Self:
        return cls(trace_id=trace_id, status=OperationStatus.REJECTED, error=error)

    @classmethod
    def requires_manual_intervention(cls, *, trace_id: str, error: PublicError) -> Self:
        return cls(trace_id=trace_id, status=OperationStatus.REQUIRES_MANUAL_INTERVENTION, error=error)


def status_fields_problem(*, operation: Operation) -> str | None:
    if (operation.error is None) != (operation.status in STATUSES_WITHOUT_ERROR):
        return "must have an error" if operation.error is None else "cannot have an error"
    if operation.database is not None and operation.status is not OperationStatus.SUCCEEDED:
        return "cannot have a database"
    if operation.not_rolled_back is not None and operation.status not in STATUSES_WITH_REMAINING_RESOURCES:
        return "cannot list resources that were not rolled back"
    if operation.status is OperationStatus.ROLLED_BACK and operation.not_rolled_back:
        return "cannot list resources that were not rolled back"
    return None
