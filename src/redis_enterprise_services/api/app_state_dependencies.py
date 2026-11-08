from typing import cast

from fastapi import Request

from redis_enterprise_services.creation.database_creation import DatabaseCreation
from redis_enterprise_services.operations.operation_store import OperationStore


def database_creation(request: Request) -> DatabaseCreation:
    return cast(DatabaseCreation, request.app.state.database_creation)


def operation_store(request: Request) -> OperationStore:
    return cast(OperationStore, request.app.state.operation_store)
