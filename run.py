import uvicorn

from redis_enterprise_services.config.server_settings import ServerSettings
from redis_enterprise_services.config.settings import load_settings

if __name__ == "__main__":
    server: ServerSettings = load_settings().server
    uvicorn.run(
        app="redis_enterprise_services.app:create_app", factory=True, host=server.host, port=server.port
    )
