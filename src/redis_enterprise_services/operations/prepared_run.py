from collections.abc import Callable
from typing import Final


class PreparedRun:
    def __init__(self, *, task_name: str, task: Callable[[], object]) -> None:
        self.task_name: Final[str] = task_name
        self.task: Final[Callable[[], object]] = task
