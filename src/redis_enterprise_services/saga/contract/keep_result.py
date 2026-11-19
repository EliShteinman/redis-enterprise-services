from typing import Protocol


class KeepResult[TResult](Protocol):
    def __call__(self, *, result: TResult) -> None: ...
