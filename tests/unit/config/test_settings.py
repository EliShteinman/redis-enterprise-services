import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from redis_enterprise_services.config.settings import load_settings

API_PORT_LINE: str = "    api_port: 9443\n"


def test_the_shipped_config_files_load(config_dir: Path) -> None:
    assert load_settings(config_dir=config_dir).clusters


def test_a_cluster_that_cannot_be_configured_is_refused_when_the_config_loads(
    config_dir: Path, tmp_path: Path
) -> None:
    without_api_port: Path = tmp_path / "config"
    shutil.copytree(src=config_dir, dst=without_api_port)
    clusters_file: Path = without_api_port / "clusters.yaml"
    clusters_file.write_text(
        data=clusters_file.read_text(encoding="utf-8").replace(API_PORT_LINE, ""), encoding="utf-8"
    )

    with pytest.raises(expected_exception=ValidationError, match="has no api_port"):
        load_settings(config_dir=without_api_port)
