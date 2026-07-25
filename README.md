# Funky Python SDK

The Python client for building and running agents with [Funky](https://funky.dev).
It provides matching synchronous and asynchronous APIs for agents, environments,
sessions, and session events.

> The SDK is currently an alpha. It covers Funky's `/v1` data-plane API and intentionally
> does not expose organization, project, membership, API-key, or other `/console/v1`
> administration APIs.

## Installation

```bash
pip install funky-sdk
```

Funky supports Python 3.10 and newer.

## Quick start

Set an API key provisioned through Funky:

```bash
export FUNKY_API_KEY=fk_...
```

Then create reusable agent and environment configurations, and start a session:

```python
from funky import Funky

with Funky() as client:
    agent = client.agents.create(
        name="Repository investigator",
        system_prompt="You are a careful coding agent. Verify claims with tools.",
        model={"provider": "anthropic", "model": "claude-sonnet-5"},
        tool_policy={"max_iterations": 20},
    )

    environment = client.environments.create(
        name="github-access",
        network={
            "type": "limited",
            "allowed_hosts": ["github.com", "*.githubusercontent.com"],
        },
    )

    session = client.sessions.create(
        agent=agent.id,
        environment_id=environment.id,
        title="Investigate issue 42",
    )
    client.sessions.wait_until_ready(session.id, timeout=180)

    queued = client.sessions.send_message(
        session.id,
        content="Inspect the repository and identify the root cause.",
    )

    with client.sessions.stream_events(session.id, after_seq=queued.seq) as events:
        for event in events:
            if event.type == "assistant_message":
                for block in event.payload.content:
                    if block.type == "text":
                        print(block.text)
            elif event.type == "turn_completed":
                break
            elif event.type == "turn_failed":
                raise RuntimeError(event.payload.message)
```

Create agents and environments during application setup and retain their IDs. A new
session is appropriate for each independent run or durable conversation.

## Async client

`AsyncFunky` exposes the same resources and method names. Network operations are
awaitable, pagination uses `async for`, and streams use `async with`:

```python
from funky import AsyncFunky


async def show_events(session_id: str) -> None:
    async with AsyncFunky() as client:
        async with client.sessions.stream_events(session_id) as events:
            async for event in events:
                print(event.type, event.seq)
                if event.type in {"turn_completed", "turn_failed"}:
                    break
```

## Resource APIs

The synchronous client exposes:

```text
client.agents.create(...)
client.agents.list(...)
client.agents.iter(...)
client.agents.retrieve(agent_id)
client.agents.update(agent_id, ...)
client.agents.archive(agent_id)
client.agents.list_versions(agent_id, ...)
client.agents.iter_versions(agent_id, ...)
client.agents.retrieve_version(agent_id, version)

client.environments.create(...)
client.environments.list(...)
client.environments.iter(...)
client.environments.retrieve(environment_id)
client.environments.update(environment_id, ...)
client.environments.archive(environment_id)
client.environments.delete(environment_id)

client.sessions.create(...)
client.sessions.list(...)
client.sessions.iter(...)
client.sessions.retrieve(session_id)
client.sessions.archive(session_id)
client.sessions.send_message(session_id, content=...)
client.sessions.list_events(session_id, ...)
client.sessions.iter_events(session_id, ...)
client.sessions.stream_events(session_id, ...)
client.sessions.wait_until_ready(session_id, ...)
client.sessions.wait_for_turn(session_id, ...)
```

All API responses are dataclass models. Configuration inputs accept dictionaries; agent
models and references also have typed `ModelConfig`, `RuntimeConfig`, and
`AgentReference` forms.

Unknown future session-event and content-block variants are returned as
`UnknownSessionEvent` and `UnknownContentBlock` rather than causing parsing failures.
Their original fields are available through each model's `raw` attribute.

## Pagination

Use `list()` when page metadata matters, or the auto-paginating iterator:

```python
for agent in client.agents.iter(include_archived=True):
    print(agent.id, agent.name)

for event in client.sessions.iter_events(session_id, after_seq=0):
    print(event.seq, event.type)
```

## Errors and retries

All SDK errors inherit from `FunkyError`:

```text
FunkyError
├── APIConnectionError
│   └── APITimeoutError
└── APIStatusError
    ├── BadRequestError
    ├── AuthenticationError
    ├── PermissionDeniedError
    ├── NotFoundError
    ├── ConflictError
    ├── RateLimitError
    └── InternalServerError
```

Status errors retain `status_code`, `error_type`, `code`, `request_id`, response
`headers`, and a safely redacted `body`.

The SDK retries reads, archive operations, and creates with their stable
client-generated UUID. It does not automatically retry ambiguous agent/environment
updates or message submissions. Event streams resume from the last yielded sequence,
ignore heartbeat comments, and defensively discard replayed duplicates.

## Client configuration

```python
import httpx
from funky import Funky

http_client = httpx.Client(transport=my_transport)
client = Funky(
    api_key="fk_...",  # defaults from FUNKY_API_KEY
    base_url="https://api.funky.dev",
    timeout=30,
    max_retries=2,
    user_agent="my-service/1.0",
    http_client=http_client,  # useful for custom transports and tests
)
```

A supplied HTTP client remains owned by the caller and is not closed by `Funky`.
The SDK never includes the API key in its representation or exceptions.

## Development

```bash
uv sync --dev
uv run pytest
uvx ruff check .
uvx ruff format --check .
uv build
```
