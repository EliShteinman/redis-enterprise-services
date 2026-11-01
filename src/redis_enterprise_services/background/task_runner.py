from collections.abc import Callable
from typing import Protocol


class TaskRunner(Protocol):
    def submit(self, *, name: str, task: Callable[[], object]) -> None: ...
