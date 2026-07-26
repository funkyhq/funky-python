from __future__ import annotations

import os
from typing import Any

import httpx

from ._resources import (
    Agents,
    AsyncAgents,
    AsyncEnvironments,
    AsyncSessions,
    Environments,
    Sessions,
)
from ._transport import AsyncTransport, SyncTransport
from ._version import __version__

DEFAULT_BASE_URL = "https://api.funky.dev"


def _resolve_api_key(api_key: str | None) -> str:
    resolved = api_key if api_key is not None else os.environ.get("FUNKY_API_KEY")
    if not resolved:
        raise ValueError(
            "Funky API key is required; pass api_key or set the FUNKY_API_KEY environment variable"
        )
    return resolved


class Funky:
    """Synchronous client for the Funky data-plane API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 2,
        user_agent: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._transport = SyncTransport(
            api_key=_resolve_api_key(api_key),
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            user_agent=user_agent or f"funky-python/{__version__}",
            http_client=http_client,
        )
        self.agents = Agents(self._transport)
        self.environments = Environments(self._transport)
        self.sessions = Sessions(self._transport)

    def __repr__(self) -> str:
        return f"Funky(base_url={self._transport.base_url!r})"

    def __enter__(self) -> Funky:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def close(self) -> None:
        self._transport.close()

    def health(self) -> dict[str, str]:
        return self._transport.request("GET", "/health", retry=True)


class AsyncFunky:
    """Asynchronous client for the Funky data-plane API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 2,
        user_agent: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._transport = AsyncTransport(
            api_key=_resolve_api_key(api_key),
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            user_agent=user_agent or f"funky-python/{__version__}",
            http_client=http_client,
        )
        self.agents = AsyncAgents(self._transport)
        self.environments = AsyncEnvironments(self._transport)
        self.sessions = AsyncSessions(self._transport)

    def __repr__(self) -> str:
        return f"AsyncFunky(base_url={self._transport.base_url!r})"

    async def __aenter__(self) -> AsyncFunky:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._transport.close()

    async def health(self) -> dict[str, str]:
        return await self._transport.request("GET", "/health", retry=True)
