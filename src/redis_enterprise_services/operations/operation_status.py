from enum import StrEnum


class OperationStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"
    REQUIRES_MANUAL_INTERVENTION = "requires_manual_intervention"


CLEANLY_ENDED_STATUSES: frozenset[OperationStatus] = frozenset(
    {OperationStatus.SUCCEEDED, OperationStatus.REJECTED, OperationStatus.ROLLED_BACK}
)
STATUSES_WITHOUT_ERROR: frozenset[OperationStatus] = frozenset(
    {OperationStatus.RUNNING, OperationStatus.SUCCEEDED}
)
STATUSES_WITH_REMAINING_RESOURCES: frozenset[OperationStatus] = frozenset(
    {OperationStatus.ROLLED_BACK, OperationStatus.REQUIRES_MANUAL_INTERVENTION}
)
