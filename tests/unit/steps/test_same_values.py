from pydantic import JsonValue

from redis_enterprise_services.steps.same_values import same_values


def test_a_list_returned_in_another_order_with_reordered_keys_is_the_same() -> None:
    wanted: dict[str, JsonValue] = {
        "roles_permissions": [{"role_uid": 1, "redis_acl_uid": 2}, {"role_uid": 3, "redis_acl_uid": 4}]
    }
    stored: dict[str, JsonValue] = {
        "roles_permissions": [{"redis_acl_uid": 4, "role_uid": 3}, {"redis_acl_uid": 2, "role_uid": 1}]
    }

    assert same_values(current=stored, expected=wanted, unordered_fields=frozenset({"roles_permissions"}))


def test_a_list_whose_order_matters_is_not_the_same_in_another_order() -> None:
    wanted: dict[str, JsonValue] = {"shard_key_regex": [{"regex": "a"}, {"regex": "b"}]}
    stored: dict[str, JsonValue] = {"shard_key_regex": [{"regex": "b"}, {"regex": "a"}]}

    assert not same_values(current=stored, expected=wanted, unordered_fields=frozenset({"roles_permissions"}))


def test_a_whole_number_sent_as_a_float_is_the_same_as_the_int_the_cluster_returns() -> None:
    stored: dict[str, JsonValue] = {"memory_size": 100}

    assert same_values(current=stored, expected={"memory_size": 100.0}, unordered_fields=frozenset())
