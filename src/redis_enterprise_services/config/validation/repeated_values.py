from collections import Counter
from collections.abc import Hashable


def repeated_values[T: Hashable](*, values: list[T]) -> set[T]:
    return {value for value, count in Counter(values).items() if count > 1}


def reject_repeated[T: Hashable](*, what: str, values: list[T]) -> None:
    repeated: set[T] = repeated_values(values=values)
    if repeated:
        raise ValueError(f"{what} configured more than once: {sorted(repeated, key=str)}")
