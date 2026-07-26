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

    result = client.sessions.run_turn(
        session.id,
        content="Inspect the repository and identify the root cause.",
    )
    print(result.output_text)
```

Create agents and environments during application setup and retain their IDs. A new
session is appropriate for each independent run or durable conversation.

## Async client

`AsyncFunky` exposes the same resources and method names. Network operations are
awaitable and pagination uses `async for`. `run_turn()` manages the event stream
internally, so the common request-response path only needs the client context:

```python
from funky import AsyncFunky


async def ask_agent(session_id: str) -> None:
    async with AsyncFunky() as client:
        result = await client.sessions.run_turn(
            session_id,
            content="Summarize the repository.",
        )
        print(result.output_text)
```

`run_turn()` returns a `RunTurnResult` containing `output_text`, the message
submission, all events observed during the turn, and the terminal event. It raises
`TurnFailedError` when the agent reports a failed turn. Use `stream_events()` directly
when an application needs to process assistant messages or tool results in real time.

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
client.sessions.run_turn(session_id, content=...)
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
