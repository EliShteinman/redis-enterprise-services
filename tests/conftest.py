from pathlib import Path

import pytest

CONFIG_DIR: Path = Path(__file__).parent.parent / "helm" / "files"


@pytest.fixture(scope="session")
def config_dir() -> Path:
    return CONFIG_DIR
