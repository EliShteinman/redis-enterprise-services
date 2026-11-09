from pydantic import JsonValue

from redis_enterprise_services.resources.endpoint_resource_repository import fields_without_value

SENT: dict[str, JsonValue] = {"name": "app", "password": "p", "role_uids": [5], "email": "a@b"}


def test_every_sent_field_must_come_back_with_a_value() -> None:
    returned: dict[str, JsonValue] = {"name": "app", "role_uids": [5], "email": None}

    assert fields_without_value(sent=SENT, returned=returned, unreturned_fields=frozenset({"password"})) == [
        "email"
    ]


def test_an_empty_list_is_a_value() -> None:
    returned: dict[str, JsonValue] = {"name": "app", "role_uids": [], "email": "a@b"}

    assert fields_without_value(sent=SENT, returned=returned, unreturned_fields=frozenset({"password"})) == []
