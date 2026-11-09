import pytest
from pydantic import ValidationError

from redis_enterprise_services.databases.new_database import NewDatabase
from redis_enterprise_services.planning.database_spec import DatabaseSpec, DatabaseUserSpec

DATABASE: NewDatabase = NewDatabase(name="orders", memory_size=104857600)


def user(*, name: str) -> DatabaseUserSpec:
    return DatabaseUserSpec(name=name, password="s3cret", acl_rule="+@all ~orders:*")


def test_a_user_requested_twice_is_refused() -> None:
    with pytest.raises(expected_exception=ValidationError):
        DatabaseSpec(database=DATABASE, users=[user(name="app"), user(name="app")])


def test_a_user_name_with_the_name_separator_is_refused() -> None:
    with pytest.raises(expected_exception=ValidationError):
        user(name="app-reader")
