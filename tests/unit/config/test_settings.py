from pathlib import Path

from redis_enterprise_services.config.settings import load_settings


def test_the_shipped_config_files_load(config_dir: Path) -> None:
    assert load_settings(config_dir=config_dir).clusters
