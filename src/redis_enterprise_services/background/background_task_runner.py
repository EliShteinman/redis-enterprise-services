from collections.abc import Callable
from typing import Protocol


class BackgroundTaskRunner(Protocol):
    def submit(self, *, name: str, task: Callable[[], object]) -> None: ...
