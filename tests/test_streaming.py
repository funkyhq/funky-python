from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from conftest import event_json

from funky import AsyncFunky, Funky, NotFoundError


def sse(*events: dict) -> str:
    return "".join(
        f":hb\nid: {event['seq']}\nevent: {event['type']}\ndata: {json.dumps(event)}\n\n"
        for event in events
    )


def test_stream_reconnects_with_last_event_id_and_deduplicates(
    monkeypatch: pytest.MonkeyPatch,
):
    requests: list[httpx.Request] = []
    first = event_json(1, "session_provisioned", {})
    duplicate = event_json(1, "session_provisioned", {})
    terminal = event_json(2, "turn_completed", {})

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = sse(first) if len(requests) == 1 else sse(duplicate, terminal)
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    monkeypatch.setattr("funky._streaming.retry_delay", lambda *_: 0)
    client = Funky(
        api_key="fk_test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    yielded = []
    with client.sessions.stream_events("session-1") as stream:
        for event in stream:
            yielded.append(event)
            if event.type == "turn_completed":
                break

    assert [event.seq for event in yielded] == [1, 2]
    assert requests[0].url.params["after_seq"] == "0"
    assert requests[1].headers["last-event-id"] == "1"


def test_stream_surfaces_http_error_before_opening():
    client = Funky(
        api_key="fk_test",
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    404,
                    json={
                        "error": {"type": "not_found_error", "message": "missing"},
                        "request_id": "req-1",
                    },
                )
            )
        ),
    )
    with pytest.raises(NotFoundError):
        with client.sessions.stream_events("session-1") as stream:
            next(iter(stream))


@pytest.mark.asyncio
async def test_async_stream_parses_events_and_closes():
    terminal = event_json(4, "turn_completed", {})

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text=sse(terminal), headers={"content-type": "text/event-stream"}
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = AsyncFunky(api_key="fk_test", http_client=http_client)
    seen = []
    async with client.sessions.stream_events("session-1", after_seq=3) as stream:
        async for event in stream:
            seen.append(event)
            break
    assert [event.seq for event in seen] == [4]
    await http_client.aclose()


@pytest.mark.asyncio
async def test_async_stream_cancellation_closes_response():
    response_closed = asyncio.Event()

    class HangingStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b":hb\n\n"
            await asyncio.Event().wait()

        async def aclose(self) -> None:
            response_closed.set()

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            stream=HangingStream(),
            headers={"content-type": "text/event-stream"},
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = AsyncFunky(api_key="fk_test", http_client=http_client)
    stream = client.sessions.stream_events("session-1")

    async def consume() -> None:
        async with stream:
            async for _ in stream:
                pass

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert response_closed.is_set()
    await http_client.aclose()
