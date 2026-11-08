from enum import StrEnum


class AbandonedMarkResult(StrEnum):
    MARKED = "marked"
    NOT_ABANDONED = "not_abandoned"
    SAGA_CHANGED = "saga_changed"
