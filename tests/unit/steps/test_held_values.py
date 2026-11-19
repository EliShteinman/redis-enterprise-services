from redis_enterprise_services.steps.held_values import HeldValues, held_values


def test_values_equal_to_both_the_new_and_the_old_are_held_as_both() -> None:
    assert (
        held_values(
            current={"roles": [1]},
            new_values={"roles": [1]},
            old_values={"roles": [1]},
            order_insensitive_fields=frozenset(),
        )
        is HeldValues.BOTH
    )
