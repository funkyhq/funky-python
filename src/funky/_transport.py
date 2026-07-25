from __future__ import annotations

import asyncio
import random
import re
import time
from collections.abc import Mapping
from typing import Any

import httpx

from ._exceptions import APIConnectionError, APITimeoutError, status_error

_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
_SENSITIVE_KEYS = {"api_key", "authorization", "token", "secret"}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.lower() in _SENSITIVE_KEYS else _redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return re.sub(r"\bfk_[A-Za-z0-9_-]+\b", "[REDACTED]", value)
    return value


def response_payload(response: httpx.Response) -> Any:
    if response.status_code == 204 or not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text[:20_000]}


def raise_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    payload = _redact(response_payload(response))
    raise status_error(response.status_code, payload=payload, headers=response.headers)


def retry_delay(response: httpx.Response | None, attempt: int) -> float:
    if response is not None:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
    ceiling = min(8.0, 0.5 * (2 ** min(attempt, 4)))
    return random.uniform(0.0, ceiling)


class SyncTransport:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout: float,
        max_retries: int,
        user_agent: str,
        http_client: httpx.Client | None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": user_agent,
            "Accept": "application/json",
        }
        self.client = http_client or httpx.Client()
        self._owns_client = http_client is None

    def url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        retry: bool = False,
        retry_connect_only: bool = False,
    ) -> Any:
        attempts = self.max_retries + 1 if retry or retry_connect_only else 1
        for attempt in range(attempts):
            response: httpx.Response | None = None
            try:
                response = self.client.request(
                    method,
                    self.url(path),
                    params=params,
                    json=json,
                    headers=self.headers,
                    timeout=self.timeout,
                )
            except httpx.TimeoutException as exc:
                is_pre_send = isinstance(exc, (httpx.ConnectTimeout, httpx.PoolTimeout))
                should_retry = attempt + 1 < attempts and (
                    retry or (retry_connect_only and is_pre_send)
                )
                if should_retry:
                    time.sleep(retry_delay(None, attempt))
                    continue
                raise APITimeoutError("Request to the Funky API timed out") from exc
            except httpx.RequestError as exc:
                is_pre_send = isinstance(exc, httpx.ConnectError)
                should_retry = attempt + 1 < attempts and (
                    retry or (retry_connect_only and is_pre_send)
                )
                if should_retry:
                    time.sleep(retry_delay(None, attempt))
                    continue
                raise APIConnectionError("Could not connect to the Funky API") from exc

            assert response is not None
            if retry and response.status_code in _RETRYABLE_STATUSES and attempt + 1 < attempts:
                time.sleep(retry_delay(response, attempt))
                continue
            raise_for_status(response)
            return response_payload(response)
        raise AssertionError("unreachable")

    def close(self) -> None:
        if self._owns_client:
            self.client.close()


class AsyncTransport:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout: float,
        max_retries: int,
        user_agent: str,
        http_client: httpx.AsyncClient | None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": user_agent,
            "Accept": "application/json",
        }
        self.client = http_client or httpx.AsyncClient()
        self._owns_client = http_client is None

    def url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        retry: bool = False,
        retry_connect_only: bool = False,
    ) -> Any:
        attempts = self.max_retries + 1 if retry or retry_connect_only else 1
        for attempt in range(attempts):
            response: httpx.Response | None = None
            try:
                response = await self.client.request(
                    method,
                    self.url(path),
                    params=params,
                    json=json,
                    headers=self.headers,
                    timeout=self.timeout,
                )
            except httpx.TimeoutException as exc:
                is_pre_send = isinstance(exc, (httpx.ConnectTimeout, httpx.PoolTimeout))
                should_retry = attempt + 1 < attempts and (
                    retry or (retry_connect_only and is_pre_send)
                )
                if should_retry:
                    await asyncio.sleep(retry_delay(None, attempt))
                    continue
                raise APITimeoutError("Request to the Funky API timed out") from exc
            except httpx.RequestError as exc:
                is_pre_send = isinstance(exc, httpx.ConnectError)
                should_retry = attempt + 1 < attempts and (
                    retry or (retry_connect_only and is_pre_send)
                )
                if should_retry:
                    await asyncio.sleep(retry_delay(None, attempt))
                    continue
                raise APIConnectionError("Could not connect to the Funky API") from exc

            assert response is not None
            if retry and response.status_code in _RETRYABLE_STATUSES and attempt + 1 < attempts:
                await asyncio.sleep(retry_delay(response, attempt))
                continue
            raise_for_status(response)
            return response_payload(response)
        raise AssertionError("unreachable")

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()
