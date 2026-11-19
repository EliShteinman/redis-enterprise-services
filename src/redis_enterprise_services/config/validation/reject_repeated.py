from collections.abc import Hashable

from redis_enterprise_services.sequences.repeated_values import repeated_values


def reject_repeated[T: Hashable](*, what: str, values: list[T]) -> None:
    repeated: set[T] = repeated_values(values=values)
    if repeated:
        raise ValueError(f"{what} configured more than once: {sorted(repeated, key=str)}")
