from pydantic import JsonValue

from redis_enterprise_services.steps.same_values import fields_not_holding, same_values


def test_a_list_returned_in_another_order_with_reordered_keys_is_the_same() -> None:
    expected: dict[str, JsonValue] = {
        "roles_permissions": [{"role_uid": 1, "redis_acl_uid": 2}, {"role_uid": 3, "redis_acl_uid": 4}]
    }
    current: dict[str, JsonValue] = {
        "roles_permissions": [{"redis_acl_uid": 4, "role_uid": 3}, {"redis_acl_uid": 2, "role_uid": 1}]
    }

    assert same_values(
        current=current, expected=expected, order_insensitive_fields=frozenset({"roles_permissions"})
    )


def test_a_list_whose_order_matters_is_not_the_same_in_another_order() -> None:
    expected: dict[str, JsonValue] = {"shard_key_regex": [{"regex": "a"}, {"regex": "b"}]}
    current: dict[str, JsonValue] = {"shard_key_regex": [{"regex": "b"}, {"regex": "a"}]}

    assert not same_values(
        current=current, expected=expected, order_insensitive_fields=frozenset({"roles_permissions"})
    )


def test_a_whole_number_sent_as_a_float_is_the_same_as_the_int_the_cluster_returns() -> None:
    current: dict[str, JsonValue] = {"memory_size": 100}

    assert same_values(current=current, expected={"memory_size": 100.0}, order_insensitive_fields=frozenset())


def test_permissions_set_earlier_must_be_on_the_database_in_any_order() -> None:
    held: dict[str, JsonValue] = {
        "roles_permissions": [{"role_uid": 2, "redis_acl_uid": 3}, {"role_uid": 4, "redis_acl_uid": 5}]
    }
    expected: dict[str, JsonValue] = {
        "roles_permissions": [{"role_uid": 4, "redis_acl_uid": 5}, {"role_uid": 2, "redis_acl_uid": 3}]
    }

    assert (
        fields_not_holding(
            current=held, expected=expected, order_insensitive_fields=frozenset({"roles_permissions"})
        )
        == []
    )


def test_a_missing_permission_is_reported() -> None:
    held: dict[str, JsonValue] = {"roles_permissions": []}
    expected: dict[str, JsonValue] = {"roles_permissions": [{"role_uid": 4, "redis_acl_uid": 5}]}

    assert fields_not_holding(current=held, expected=expected, order_insensitive_fields=frozenset()) == [
        "roles_permissions"
    ]
