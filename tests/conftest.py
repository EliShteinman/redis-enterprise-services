import shutil
from pathlib import Path

import pytest

CONFIG_DIR: Path = Path(__file__).parent.parent / "helm" / "files"


@pytest.fixture(scope="session")
def config_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory: Path = tmp_path_factory.mktemp("config")
    for file in CONFIG_DIR.glob("*.yaml"):
        shutil.copy(file, directory / file.name.replace("clusters.example.yaml", "clusters.yaml"))
    return directory
