import pytest
from pydantic import ValidationError

from redis_enterprise_services.config.database_defaults_settings import (
    DatabaseDefaultsSettings,
    DatabaseKind,
    OverrideSelector,
)


def test_an_override_selector_without_a_label_is_refused() -> None:
    with pytest.raises(expected_exception=ValidationError):
        OverrideSelector.model_validate(obj={})


def test_every_kind_of_database_names_a_set_of_defaults() -> None:
    assert set(DatabaseKind) == set(DatabaseDefaultsSettings.model_fields)
