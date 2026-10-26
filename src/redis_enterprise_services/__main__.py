import logging

from redis_enterprise_services.config import load_settings
from redis_enterprise_services.logger import configure_logging

logger: logging.Logger = logging.getLogger(name=__name__)


def main() -> None:
    configure_logging(settings=load_settings().log)
    logger.info(msg="redis-enterprise-services started")


if __name__ == "__main__":
    main()
