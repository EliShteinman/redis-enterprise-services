from pathlib import Path

import yaml
from pydantic import ValidationError
from pydantic_settings import SettingsError

from redis_enterprise_services.config.settings import CONFIG_FILE, Settings
from redis_enterprise_services.exceptions import ConfigurationError


def load_settings() -> Settings:
    if not Path(CONFIG_FILE).is_file():
        raise ConfigurationError(reason=f"{CONFIG_FILE} not found in {Path.cwd()}")
    try:
        return Settings()
    except ValidationError as error:
        raise ConfigurationError(reason=fields_in_error(error=error)) from None
    except (SettingsError, yaml.YAMLError) as error:
        raise ConfigurationError(reason=str(error)) from error


def fields_in_error(*, error: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in detail['loc'])}: {detail['msg']}"
        for detail in error.errors(include_input=False, include_url=False)
    )
