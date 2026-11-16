import asyncio
import logging
from collections.abc import Iterator
from contextvars import Token

import pytest
from starlette.types import Message, Receive, Scope, Send

from redis_enterprise_services.logger.quiet import QuietPathsMiddleware, QuietRequestFilter, quiet_request

QUIET_PATHS: frozenset[str] = frozenset({"/health"})
INFO_RECORD: logging.LogRecord = logging.makeLogRecord(
    dict={"msg": "GET /health 200", "levelno": logging.INFO}
)
WARNING_RECORD: logging.LogRecord = logging.makeLogRecord(dict={"msg": "slow", "levelno": logging.WARNING})
QUIET_FILTER: QuietRequestFilter = QuietRequestFilter(kept_level="WARNING")


async def no_message() -> Message:
    return {"type": "http.request"}


async def ignore(message: Message) -> None:
    return None


def quiet_while_handling(*, path: str) -> bool:
    seen: list[bool] = []

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        seen.append(quiet_request.get())

    middleware: QuietPathsMiddleware = QuietPathsMiddleware(app, paths=QUIET_PATHS)
    asyncio.run(main=middleware({"type": "http", "path": path}, no_message, ignore))
    return seen[0]


@pytest.fixture
def inside_a_quiet_request() -> Iterator[None]:
    token: Token[bool] = quiet_request.set(True)
    yield
    quiet_request.reset(token)


def test_a_quiet_path_is_handled_quietly() -> None:
    assert quiet_while_handling(path="/health")


@pytest.mark.parametrize("path", ["/", "/health/x", "/v1/databases"])
def test_other_paths_are_not_quiet(path: str) -> None:
    assert not quiet_while_handling(path=path)


@pytest.mark.usefixtures("inside_a_quiet_request")
def test_records_of_a_quiet_request_are_dropped() -> None:
    assert not QUIET_FILTER.filter(INFO_RECORD)


@pytest.mark.usefixtures("inside_a_quiet_request")
def test_warnings_of_a_quiet_request_are_kept() -> None:
    assert QUIET_FILTER.filter(WARNING_RECORD)


def test_records_of_other_requests_are_kept() -> None:
    assert QUIET_FILTER.filter(INFO_RECORD)
