import importlib
import pkgutil

import redis_enterprise_services.exceptions as exceptions_package
from redis_enterprise_services.config.settings import load_settings
from redis_enterprise_services.exceptions.base import RedisEnterpriseServicesError

CODES_WITHOUT_PUBLIC_MAPPING: set[str] = {"internal_error", "operation_not_found"}


def every_subclass(parent: type[RedisEnterpriseServicesError]) -> list[type[RedisEnterpriseServicesError]]:
    children: list[type[RedisEnterpriseServicesError]] = parent.__subclasses__()
    return children + [grandchild for child in children for grandchild in every_subclass(child)]


def import_all_exception_codes() -> set[str]:
    for module in pkgutil.iter_modules(exceptions_package.__path__):
        importlib.import_module(name=f"{exceptions_package.__name__}.{module.name}")
    return {error.code for error in every_subclass(RedisEnterpriseServicesError)}


def test_every_mapped_exception_code_belongs_to_an_exception() -> None:
    assert set(load_settings().operation.public_code_by_error_code) <= import_all_exception_codes()


def test_every_exception_code_has_a_public_error_code() -> None:
    mapped: set[str] = set(load_settings().operation.public_code_by_error_code)
    assert import_all_exception_codes() - CODES_WITHOUT_PUBLIC_MAPPING <= mapped
