from collections.abc import Hashable


def repeated_values[T: Hashable](*, values: list[T]) -> set[T]:
    return {value for value in values if values.count(value) > 1}
