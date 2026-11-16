import os
import shutil
from pathlib import Path

import pytest

from redis_enterprise_services.config.settings import Settings

CONFIG_DIR: Path = Path(__file__).parent.parent / "helm" / "files"


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name in [name for name in os.environ if name.upper().startswith("RES_")]:
        monkeypatch.delenv(name=name)
    monkeypatch.setenv(name="RES_STATE__URL", value="redis://unused:unused@unused-in-unit-tests:6379")
    monkeypatch.setenv(name="RES_STATE__KEY_PREFIX", value="unused-in-unit-tests:")


@pytest.fixture(scope="session")
def config_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory: Path = tmp_path_factory.mktemp("config")
    for file in CONFIG_DIR.glob("*.yaml"):
        shutil.copy(file, directory / file.name.replace("clusters.example.yaml", "clusters.yaml"))
    return directory
