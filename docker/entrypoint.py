from redis_enterprise_services.config.config_location import ConfigLocation
from redis_enterprise_services.config.settings import load_settings
from redis_enterprise_services.server import serve

if __name__ == "__main__":
    location: ConfigLocation = ConfigLocation()  # pyright: ignore[reportCallIssue]
    serve(settings=load_settings(config_dir=location.config_dir))
