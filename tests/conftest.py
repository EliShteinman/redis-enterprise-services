import pytest


@pytest.fixture(autouse=True)
def state_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(name="RES_STATE__PASSWORD", value="unused-in-unit-tests")
