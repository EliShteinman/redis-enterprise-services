import pytest


@pytest.fixture(autouse=True)
def state_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(name="RES_STATE__PASSWORD", value="unused-in-unit-tests")
    monkeypatch.setenv(name="RES_DATABASE__DEFAULT_USER_PASSWORD", value="unused-in-unit-tests")
