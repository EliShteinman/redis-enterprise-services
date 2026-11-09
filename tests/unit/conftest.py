import os

import pytest

from redis_enterprise_services.config.settings import Settings


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name in [name for name in os.environ if name.upper().startswith("RES_")]:
        monkeypatch.delenv(name=name)
    monkeypatch.setenv(name="RES_STATE__PASSWORD", value="unused-in-unit-tests")
    monkeypatch.setenv(name="RES_DATABASE__DEFAULT_USER_PASSWORD", value="unused-in-unit-tests")
    monkeypatch.setenv(name="RES_CLUSTER_CREDENTIALS__USERNAME", value="unused-in-unit-tests")
    monkeypatch.setenv(name="RES_CLUSTER_CREDENTIALS__PASSWORD", value="unused-in-unit-tests")
