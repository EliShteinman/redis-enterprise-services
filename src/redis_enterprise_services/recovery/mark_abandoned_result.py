from enum import StrEnum


class MarkAbandonedResult(StrEnum):
    MARKED = "marked"
    NOT_ABANDONED = "not_abandoned"
    SAGA_CHANGED = "saga_changed"
