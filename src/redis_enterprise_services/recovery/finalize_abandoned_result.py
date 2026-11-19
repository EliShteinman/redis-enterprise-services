from enum import StrEnum


class FinalizeAbandonedResult(StrEnum):
    FINALIZED = "finalized"
    NOT_ABANDONED = "not_abandoned"
    SAGA_CHANGED = "saga_changed"
