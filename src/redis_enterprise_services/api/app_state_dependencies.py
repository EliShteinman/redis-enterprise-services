from typing import cast

from fastapi import Request

from redis_enterprise_services.config.api_settings import ApiSettings
from redis_enterprise_services.config.settings import Settings
from redis_enterprise_services.creation.database_creation import DatabaseCreation
from redis_enterprise_services.operations.operation_store import OperationStore


def database_creation_from_app_state(request: Request) -> DatabaseCreation:
    return cast(DatabaseCreation, request.app.state.database_creation)


def operation_store_from_app_state(request: Request) -> OperationStore:
    return cast(OperationStore, request.app.state.operation_store)


def api_settings_from_app_state(request: Request) -> ApiSettings:
    return cast(Settings, request.app.state.settings).api
