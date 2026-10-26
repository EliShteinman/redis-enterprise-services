import logging
import sys

from redis_enterprise_services.config import Settings, load_settings
from redis_enterprise_services.exceptions import ConfigurationError
from redis_enterprise_services.logger import configure_logging

CONFIGURATION_ERROR_EXIT_CODE: int = 2

logger: logging.Logger = logging.getLogger(name=__name__)


def main() -> None:
    try:
        settings: Settings = load_settings()
    except ConfigurationError as error:
        print(error, file=sys.stderr)
        raise SystemExit(CONFIGURATION_ERROR_EXIT_CODE) from None
    configure_logging(settings=settings.log)
    logger.info(msg="redis-enterprise-services started")


if __name__ == "__main__":
    main()
