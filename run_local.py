from pathlib import Path

from redis_enterprise_services.config.settings import load_settings
from redis_enterprise_services.server import serve

LOCAL_CONFIG_DIR: Path = Path("helm/files")

if __name__ == "__main__":
    serve(settings=load_settings(config_dir=LOCAL_CONFIG_DIR))
