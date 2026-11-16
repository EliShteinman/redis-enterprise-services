from collections import Counter
from collections.abc import Hashable


def repeated_values[T: Hashable](*, values: list[T]) -> set[T]:
    return {value for value, count in Counter(values).items() if count > 1}
