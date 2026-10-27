from collections.abc import Callable

type KeepResult[TResult] = Callable[[TResult], None]
