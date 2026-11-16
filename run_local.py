from pathlib import Path

import uvicorn

from redis_enterprise_services.app import create_app
from redis_enterprise_services.config.settings import Settings, load_settings

LOCAL_CONFIG_DIR: Path = Path("helm/files")

if __name__ == "__main__":
    settings: Settings = load_settings(config_dir=LOCAL_CONFIG_DIR)
    uvicorn.run(
        app=create_app(settings=settings),
        host=settings.server.host,
        port=settings.server.port,
        log_config=None,
    )
