from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import AsyncIterator, Iterator
from typing import Any
from urllib.parse import quote

import httpx

from ._exceptions import APIConnectionError, APITimeoutError
from ._models import SessionEvent, session_event_from_dict
from ._transport import AsyncTransport, SyncTransport, raise_for_status, retry_delay


def _frames(lines: Iterator[str]) -> Iterator[dict[str, str]]:
    frame: dict[str, str] = {}
    data_lines: list[str] = []
    for line in lines:
        if line == "":
            if data_lines:
                frame["data"] = "\n".join(data_lines)
                yield frame
            frame = {}
            data_lines = []
            continue
        if line.startswith(":"):
            continue
        field, separator, value = line.partition(":")
        if not separator:
            value = ""
        elif value.startswith(" "):
            value = value[1:]
        if field == "data":
            data_lines.append(value)
        elif field in {"id", "event", "retry"}:
            frame[field] = value
    if data_lines:
        frame["data"] = "\n".join(data_lines)
        yield frame


async def _aframes(lines: AsyncIterator[str]) -> AsyncIterator[dict[str, str]]:
    frame: dict[str, str] = {}
    data_lines: list[str] = []
    async for line in lines:
        if line == "":
            if data_lines:
                frame["data"] = "\n".join(data_lines)
                yield frame
            frame = {}
            data_lines = []
            continue
        if line.startswith(":"):
            continue
        field, separator, value = line.partition(":")
        if not separator:
            value = ""
        elif value.startswith(" "):
            value = value[1:]
        if field == "data":
            data_lines.append(value)
        elif field in {"id", "event", "retry"}:
            frame[field] = value
    if data_lines:
        frame["data"] = "\n".join(data_lines)
        yield frame


class EventStream:
    """A resumable synchronous SSE event stream."""

    def __init__(self, transport: SyncTransport, session_id: str, *, after_seq: int = 0) -> None:
        self._transport = transport
        self._session_id = session_id
        self._initial_after_seq = after_seq
        self._cursor = after_seq
        self._seen: set[tuple[str, int]] = set()
        self._closed = threading.Event()
        self._response: httpx.Response | None = None

    def __enter__(self) -> EventStream:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def __iter__(self) -> Iterator[SessionEvent]:
        failures = 0
        first_request = True
        while not self._closed.is_set():
            headers = {
                **self._transport.headers,
                "Accept": "text/event-stream",
            }
            params = None
            if first_request:
                params = {"after_seq": self._initial_after_seq}
            else:
                headers["Last-Event-ID"] = str(self._cursor)
            first_request = False
            try:
                timeout = httpx.Timeout(self._transport.timeout, read=None)
                with self._transport.client.stream(
                    "GET",
                    self._transport.url(
                        f"/v1/sessions/{quote(self._session_id, safe='')}/events/stream"
                    ),
                    params=params,
                    headers=headers,
                    timeout=timeout,
                ) as response:
                    self._response = response
                    if not response.is_success:
                        response.read()
                        raise_for_status(response)
                    for frame in _frames(response.iter_lines()):
                        if self._closed.is_set():
                            return
                        raw = json.loads(frame["data"])
                        event = session_event_from_dict(raw)
                        event_key = (event.session_id, event.seq)
                        if event_key in self._seen:
                            continue
                        self._seen.add(event_key)
                        self._cursor = max(self._cursor, event.seq)
                        failures = 0
                        yield event
            except (httpx.TimeoutException, httpx.RequestError, httpx.StreamError):
                if self._closed.is_set():
                    return
                failures += 1
                time.sleep(retry_delay(None, failures - 1))
                continue
            finally:
                self._response = None
            if not self._closed.is_set():
                failures += 1
                time.sleep(retry_delay(None, failures - 1))
        if failures:
            raise APIConnectionError("Funky event stream disconnected")

    def close(self) -> None:
        self._closed.set()
        if self._response is not None:
            self._response.close()


class AsyncEventStream:
    """A resumable asynchronous SSE event stream."""

    def __init__(self, transport: AsyncTransport, session_id: str, *, after_seq: int = 0) -> None:
        self._transport = transport
        self._session_id = session_id
        self._initial_after_seq = after_seq
        self._cursor = after_seq
        self._seen: set[tuple[str, int]] = set()
        self._closed = False
        self._response: httpx.Response | None = None

    async def __aenter__(self) -> AsyncEventStream:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()

    def __aiter__(self) -> AsyncIterator[SessionEvent]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[SessionEvent]:
        failures = 0
        first_request = True
        while not self._closed:
            headers = {
                **self._transport.headers,
                "Accept": "text/event-stream",
            }
            params = None
            if first_request:
                params = {"after_seq": self._initial_after_seq}
            else:
                headers["Last-Event-ID"] = str(self._cursor)
            first_request = False
            try:
                timeout = httpx.Timeout(self._transport.timeout, read=None)
                async with self._transport.client.stream(
                    "GET",
                    self._transport.url(
                        f"/v1/sessions/{quote(self._session_id, safe='')}/events/stream"
                    ),
                    params=params,
                    headers=headers,
                    timeout=timeout,
                ) as response:
                    self._response = response
                    if not response.is_success:
                        await response.aread()
                        raise_for_status(response)
                    async for frame in _aframes(response.aiter_lines()):
                        if self._closed:
                            return
                        raw = json.loads(frame["data"])
                        event = session_event_from_dict(raw)
                        event_key = (event.session_id, event.seq)
                        if event_key in self._seen:
                            continue
                        self._seen.add(event_key)
                        self._cursor = max(self._cursor, event.seq)
                        failures = 0
                        yield event
            except asyncio.CancelledError:
                await self.aclose()
                raise
            except (httpx.TimeoutException, httpx.RequestError, httpx.StreamError):
                if self._closed:
                    return
                failures += 1
                await asyncio.sleep(retry_delay(None, failures - 1))
                continue
            finally:
                self._response = None
            if not self._closed:
                failures += 1
                await asyncio.sleep(retry_delay(None, failures - 1))
        if failures:
            raise APITimeoutError("Funky event stream disconnected")

    async def aclose(self) -> None:
        self._closed = True
        if self._response is not None:
            await self._response.aclose()
