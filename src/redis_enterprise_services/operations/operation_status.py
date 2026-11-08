from enum import StrEnum


class OperationStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"
    REQUIRES_MANUAL_INTERVENTION = "requires_manual_intervention"


EXPIRING_STATUSES: frozenset[OperationStatus] = frozenset(
    {OperationStatus.SUCCEEDED, OperationStatus.REJECTED, OperationStatus.ROLLED_BACK}
)
