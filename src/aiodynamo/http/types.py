from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Request:
    method: Literal["GET"] | Literal["POST"] | Literal["PUT"]
    url: str
    headers: dict[str, str] | None
    body: bytes | None


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes


@dataclass
class RequestFailed(Exception):
    inner: Exception


HttpImplementation = Callable[[Request], Awaitable[Response]]
