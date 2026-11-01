from enum import StrEnum


class MarkResult(StrEnum):
    MARKED = "marked"
    SKIPPED = "skipped"
    SAGA_CHANGED = "saga_changed"
