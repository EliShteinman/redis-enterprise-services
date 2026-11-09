import pytest
from pydantic import ValidationError

from redis_enterprise_services.planning.database_spec import DatabaseUserSpec

ACCEPTED_BY_REDIS: list[str] = [
    "+@all ~*",
    "+@all -@dangerous ~*",
    "+get +set ~orders:*",
    "+config|get ~*",
    "%R~cache:* %W~log:*",
    "%RW~x:*",
    "allkeys allcommands",
    "nocommands",
    "+@all ~* &*",
    "+@all ~a[bc]*",
    "+@all",
    "~*",
    "+@all  ~*",
    " +@all ~* ",
    "+@all ~",
    "on +@all ~*",
    "(+get ~a*)",
    "+@all ~* (+set ~b*)",
    "+@all\t~*",
]
REFUSED_BY_REDIS: list[str] = ["", "@all ~*", "+@all *", ">secret +@all ~*", "nopass +@all ~*"]


def user(*, acl_rule: str) -> DatabaseUserSpec:
    return DatabaseUserSpec(name="app", password="S3cure-Passw0rd", acl_rule=acl_rule)


@pytest.mark.parametrize(argnames="acl_rule", argvalues=ACCEPTED_BY_REDIS)
def test_a_rule_redis_accepts_is_accepted(acl_rule: str) -> None:
    user(acl_rule=acl_rule)


@pytest.mark.parametrize(argnames="acl_rule", argvalues=REFUSED_BY_REDIS)
def test_a_rule_redis_refuses_for_its_syntax_is_refused(acl_rule: str) -> None:
    with pytest.raises(expected_exception=ValidationError):
        user(acl_rule=acl_rule)


def test_a_password_shorter_than_redis_allows_is_refused() -> None:
    with pytest.raises(expected_exception=ValidationError):
        DatabaseUserSpec(name="app", password="1234567", acl_rule="+@all ~*")
