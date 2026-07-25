from __future__ import annotations

import json
from datetime import timezone

import httpx
import pytest
from conftest import agent_json, environment_json, event_json, session_json

from funky import (
    AsyncFunky,
    AuthenticationError,
    Funky,
    LimitedNetwork,
    ModelConfig,
    UnknownContentBlock,
    UnknownSessionEvent,
)


def test_create_generates_stable_id_and_retries_identical_body(monkeypatch: pytest.MonkeyPatch):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(502, json={"error": {"message": "try again"}})
        return httpx.Response(201, json=agent_json(id=json.loads(request.content)["id"]))

    monkeypatch.setattr("funky._transport.retry_delay", lambda *_: 0)
    client = Funky(
        api_key="fk_secret",
        base_url="https://example.test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    agent = client.agents.create(
        name="Research agent",
        system_prompt="Be careful.",
        model=ModelConfig(provider="anthropic", model="claude-sonnet-5"),
    )

    assert len(requests) == 2
    assert json.loads(requests[0].content) == json.loads(requests[1].content)
    assert agent.id == json.loads(requests[0].content)["id"]
    assert requests[0].headers["authorization"] == "Bearer fk_secret"
    assert agent.created_at.tzinfo == timezone.utc


@pytest.mark.parametrize("status", [200, 201])
def test_create_accepts_200_and_201(status: int):
    client = Funky(
        api_key="fk_test",
        http_client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(status, json=environment_json()))
        ),
    )
    environment = client.environments.create(name="default")
    assert environment.id == "environment-1"


def test_explicit_null_is_sent_on_update():
    body = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal body
        body = json.loads(request.content)
        return httpx.Response(200, json=agent_json(runtime=None))

    client = Funky(
        api_key="fk_test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    updated = client.agents.update("agent-1", description=None, runtime=None)
    assert body == {"description": None, "runtime": None}
    assert updated.runtime is None


def test_delete_accepts_204():
    client = Funky(
        api_key="fk_test",
        http_client=httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(204))),
    )
    assert client.environments.delete("environment-1") is None


def test_archive_is_retried_and_returns_archived_resource(monkeypatch: pytest.MonkeyPatch):
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(502, json={"error": {"message": "try again"}})
        return httpx.Response(
            200,
            json=agent_json(archived_at="2026-07-24T21:00:00.000Z"),
        )

    monkeypatch.setattr("funky._transport.retry_delay", lambda *_: 0)
    client = Funky(
        api_key="fk_test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    archived = client.agents.archive("agent-1")
    assert calls == 2
    assert archived.archived_at is not None


def test_error_mapping_and_redaction():
    response = {
        "type": "error",
        "error": {
            "type": "authentication_error",
            "message": "invalid credential fk_leaked",
            "code": "expired",
            "api_key": "fk_leaked",
        },
        "request_id": "request-1",
    }
    client = Funky(
        api_key="fk_secret",
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    401, json=response, headers={"request-id": "header-request"}
                )
            )
        ),
    )

    with pytest.raises(AuthenticationError) as caught:
        client.agents.retrieve("missing")

    assert caught.value.status_code == 401
    assert caught.value.error_type == "authentication_error"
    assert caught.value.code == "expired"
    assert caught.value.request_id == "request-1"
    assert caught.value.body["error"]["api_key"] == "[REDACTED]"
    assert "fk_leaked" not in str(caught.value)
    assert "fk_secret" not in repr(client)
    assert "fk_secret" not in str(caught.value)


def test_resource_auto_pagination_uses_last_id():
    cursors: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("after_id")
        cursors.append(cursor)
        if cursor is None:
            return httpx.Response(
                200,
                json={"data": [session_json(id="session-2")], "has_more": True, "last_id": "2"},
            )
        return httpx.Response(
            200,
            json={"data": [session_json(id="session-1")], "has_more": False, "last_id": "1"},
        )

    client = Funky(
        api_key="fk_test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert [item.id for item in client.sessions.iter()] == ["session-2", "session-1"]
    assert cursors == [None, "2"]


def test_event_pagination_uses_returned_event_sequence():
    cursors: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("after_seq")
        cursors.append(cursor)
        if cursor == "0":
            return httpx.Response(
                200,
                json={
                    "data": [
                        event_json(
                            2,
                            "user_message",
                            {"content": [{"type": "image", "x": 1}]},
                        )
                    ],
                    "has_more": True,
                    "last_seq": 10,
                },
            )
        return httpx.Response(
            200,
            json={
                "data": [event_json(3, "future_event", {"new": "value"})],
                "has_more": False,
                "last_seq": 10,
            },
        )

    client = Funky(
        api_key="fk_test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    events = list(client.sessions.iter_events("session-1"))
    assert cursors == ["0", "2"]
    assert isinstance(events[0].payload.content[0], UnknownContentBlock)
    assert events[0].payload.content[0].raw["x"] == 1
    assert isinstance(events[1], UnknownSessionEvent)
    assert events[1].raw["payload"] == {"new": "value"}


def test_message_202_response_is_typed_and_not_retried():
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(202, json={"turn": "queued", "seq": 2})

    client = Funky(
        api_key="fk_test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    result = client.sessions.send_message("session-1", content="Hello")
    assert (result.turn, result.seq, calls) == ("queued", 2, 1)


def test_wait_until_ready():
    statuses = iter(["provisioning", "ready"])

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=session_json(status=next(statuses)))

    client = Funky(
        api_key="fk_test",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert (
        client.sessions.wait_until_ready("session-1", timeout=1, poll_interval=0).status == "ready"
    )


@pytest.mark.asyncio
async def test_async_client_has_equivalent_resource_methods():
    seen: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.method)
        return httpx.Response(200, json=agent_json())

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = AsyncFunky(api_key="fk_test", http_client=http_client)
    agent = await client.agents.retrieve("agent-1")
    assert agent.id == "agent-1"
    assert seen == ["GET"]
    await http_client.aclose()


def test_network_model_is_typed():
    client = Funky(
        api_key="fk_test",
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200,
                    json=environment_json(
                        network={"type": "limited", "allowed_hosts": ["*.example.com"]}
                    ),
                )
            )
        ),
    )
    environment = client.environments.retrieve("environment-1")
    assert isinstance(environment.network, LimitedNetwork)
    assert environment.network.allowed_hosts == ["*.example.com"]
