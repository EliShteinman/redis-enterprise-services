import os

import pytest

from redis_enterprise_services.config import ENV_PREFIX


@pytest.fixture(autouse=True)
def no_settings_from_the_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in os.environ:
        if name.upper().startswith(ENV_PREFIX):
            monkeypatch.delenv(name=name)
