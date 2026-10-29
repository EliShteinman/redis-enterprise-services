from typing import Protocol


class DatabaseLock(Protocol):
    def acquire(self, *, keys: list[str], owner: str) -> None: ...

    def release(self, *, keys: list[str], owner: str) -> None: ...
