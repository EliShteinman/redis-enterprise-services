from redis_enterprise_services.config.repeated_values import repeated_values


def test_a_value_seen_more_than_once_is_reported_once() -> None:
    assert repeated_values(values=["a", "b", "a", "a"]) == {"a"}
