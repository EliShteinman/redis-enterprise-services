from pydantic import JsonValue

from redis_enterprise_services.steps.same_values import same_values


def test_a_list_returned_in_another_order_with_reordered_keys_is_the_same() -> None:
    wanted: dict[str, JsonValue] = {
        "roles_permissions": [{"role_uid": 1, "redis_acl_uid": 2}, {"role_uid": 3, "redis_acl_uid": 4}]
    }
    stored: dict[str, JsonValue] = {
        "roles_permissions": [{"redis_acl_uid": 4, "role_uid": 3}, {"redis_acl_uid": 2, "role_uid": 1}]
    }

    assert same_values(stored=stored, wanted=wanted)
