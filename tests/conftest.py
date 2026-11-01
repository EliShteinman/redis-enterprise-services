import pytest

from redis_enterprise_services.config.settings import Settings


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    monkeypatch.setenv(name="RES_STATE__PASSWORD", value="unused-in-unit-tests")
    monkeypatch.setenv(name="RES_DATABASE__DEFAULT_USER_PASSWORD", value="unused-in-unit-tests")
    monkeypatch.setenv(name="RES_CLUSTER_ACCESS__USERNAME", value="unused-in-unit-tests")
    monkeypatch.setenv(name="RES_CLUSTER_ACCESS__PASSWORD", value="unused-in-unit-tests")
