from pydantic import JsonValue

from redis_enterprise_services.resources.cluster_object_body import without_fields
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


def test_secret_fields_are_dropped_and_the_rest_kept() -> None:
    fields: dict[str, JsonValue] = {"uid": 1, "authentication_admin_pass": "s", "port": 12000}

    assert without_fields(fields=fields, names=frozenset({"authentication_admin_pass"})) == {
        "uid": 1,
        "port": 12000,
    }
