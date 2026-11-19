import shutil
from pathlib import Path

import pytest

from redis_enterprise_services.config.config_location import CONFIG_FILE_NAMES

CONFIG_DIR: Path = Path(__file__).parent.parent / "helm" / "files"
COMMITTED_SOURCE_BY_CONFIG_FILE: dict[str, str] = {"clusters.yaml": "clusters.example.yaml"}


@pytest.fixture(scope="session")
def config_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory: Path = tmp_path_factory.mktemp("config")
    for name in CONFIG_FILE_NAMES:
        shutil.copy(CONFIG_DIR / COMMITTED_SOURCE_BY_CONFIG_FILE.get(name, name), directory / name)
    return directory
