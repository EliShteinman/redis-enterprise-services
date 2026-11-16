from pathlib import Path

CONFIG_FILE_NAMES: tuple[str, ...] = ("clusters.yaml", "defaults.yaml", "service.yaml", "redis_api.yaml")


def config_files(*, config_dir: Path) -> tuple[Path, ...]:
    return tuple(config_dir / name for name in CONFIG_FILE_NAMES)
