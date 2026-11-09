import pytest
from pydantic import ValidationError

from redis_enterprise_services.config.database_defaults_settings import OverrideClusterSelector


def test_an_override_selector_without_a_label_is_refused() -> None:
    with pytest.raises(expected_exception=ValidationError):
        OverrideClusterSelector.model_validate(obj={})
