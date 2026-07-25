from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator, Iterator, Mapping
from typing import Any
from urllib.parse import quote

from ._exceptions import APITimeoutError, FunkyError
from ._models import (
    Agent,
    AgentReference,
    AgentVersion,
    Environment,
    EventPage,
    LimitedNetwork,
    ModelConfig,
    Page,
    RuntimeConfig,
    SendMessageResponse,
    Session,
    SessionEvent,
    UnrestrictedNetwork,
    VersionPage,
    session_event_from_dict,
    to_wire,
)
from ._streaming import AsyncEventStream, EventStream
from ._transport import AsyncTransport, SyncTransport

_UNSET = object()


def _path_id(value: str) -> str:
    return quote(value, safe="")


def _params(**values: Any) -> dict[str, Any]:
    return {
        key: str(value).lower() if isinstance(value, bool) else value
        for key, value in values.items()
        if value is not None
    }


def _body(**values: Any) -> dict[str, Any]:
    return {key: to_wire(value) for key, value in values.items() if value is not _UNSET}


class Agents:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def create(
        self,
        *,
        name: str,
        system_prompt: str,
        model: ModelConfig | Mapping[str, Any],
        id: str | None = None,
        description: str | None | object = _UNSET,
        metadata: Mapping[str, str] | object = _UNSET,
        tool_policy: Mapping[str, Any] | object = _UNSET,
        runtime: RuntimeConfig | Mapping[str, Any] | None | object = _UNSET,
    ) -> Agent:
        payload = _body(
            id=id or str(uuid.uuid4()),
            name=name,
            description=description,
            metadata=metadata,
            system_prompt=system_prompt,
            model=model,
            tool_policy=tool_policy,
            runtime=runtime,
        )
        return Agent.from_dict(
            self._transport.request("POST", "/v1/agents", json=payload, retry=True)
        )

    def list(
        self,
        *,
        limit: int = 20,
        after_id: str | None = None,
        include_archived: bool = False,
    ) -> Page[Agent]:
        data = self._transport.request(
            "GET",
            "/v1/agents",
            params=_params(limit=limit, after_id=after_id, include_archived=include_archived),
            retry=True,
        )
        return Page(
            data=[Agent.from_dict(item) for item in data["data"]],
            has_more=data["has_more"],
            last_id=data.get("last_id"),
        )

    def iter(self, *, limit: int = 100, include_archived: bool = False) -> Iterator[Agent]:
        after_id = None
        while True:
            page = self.list(limit=limit, after_id=after_id, include_archived=include_archived)
            yield from page.data
            if not page.has_more or not page.last_id:
                return
            after_id = page.last_id

    def retrieve(self, agent_id: str) -> Agent:
        data = self._transport.request("GET", f"/v1/agents/{_path_id(agent_id)}", retry=True)
        return Agent.from_dict(data)

    def update(
        self,
        agent_id: str,
        *,
        name: str | object = _UNSET,
        description: str | None | object = _UNSET,
        metadata: Mapping[str, str] | object = _UNSET,
        system_prompt: str | object = _UNSET,
        model: ModelConfig | Mapping[str, Any] | object = _UNSET,
        tool_policy: Mapping[str, Any] | object = _UNSET,
        runtime: RuntimeConfig | Mapping[str, Any] | None | object = _UNSET,
    ) -> Agent:
        payload = _body(
            name=name,
            description=description,
            metadata=metadata,
            system_prompt=system_prompt,
            model=model,
            tool_policy=tool_policy,
            runtime=runtime,
        )
        if not payload:
            raise ValueError("At least one agent field must be supplied")
        data = self._transport.request("POST", f"/v1/agents/{_path_id(agent_id)}", json=payload)
        return Agent.from_dict(data)

    def archive(self, agent_id: str) -> Agent:
        data = self._transport.request(
            "POST", f"/v1/agents/{_path_id(agent_id)}/archive", retry=True
        )
        return Agent.from_dict(data)

    def list_versions(
        self,
        agent_id: str,
        *,
        limit: int = 20,
        after_version: int | None = None,
    ) -> VersionPage:
        data = self._transport.request(
            "GET",
            f"/v1/agents/{_path_id(agent_id)}/versions",
            params=_params(limit=limit, after_version=after_version),
            retry=True,
        )
        return VersionPage(
            data=[AgentVersion.from_dict(item) for item in data["data"]],
            has_more=data["has_more"],
        )

    def iter_versions(self, agent_id: str, *, limit: int = 100) -> Iterator[AgentVersion]:
        after_version = None
        while True:
            page = self.list_versions(agent_id, limit=limit, after_version=after_version)
            yield from page.data
            if not page.has_more or not page.data:
                return
            after_version = page.data[-1].version

    def retrieve_version(self, agent_id: str, version: int) -> AgentVersion:
        data = self._transport.request(
            "GET",
            f"/v1/agents/{_path_id(agent_id)}/versions/{version}",
            retry=True,
        )
        return AgentVersion.from_dict(data)


class Environments:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def create(
        self,
        *,
        name: str,
        id: str | None = None,
        description: str | None | object = _UNSET,
        metadata: Mapping[str, str] | object = _UNSET,
        network: LimitedNetwork | UnrestrictedNetwork | Mapping[str, Any] | object = _UNSET,
    ) -> Environment:
        payload = _body(
            id=id or str(uuid.uuid4()),
            name=name,
            description=description,
            metadata=metadata,
            network=network,
        )
        data = self._transport.request("POST", "/v1/environments", json=payload, retry=True)
        return Environment.from_dict(data)

    def list(
        self,
        *,
        limit: int = 20,
        after_id: str | None = None,
        include_archived: bool = False,
    ) -> Page[Environment]:
        data = self._transport.request(
            "GET",
            "/v1/environments",
            params=_params(limit=limit, after_id=after_id, include_archived=include_archived),
            retry=True,
        )
        return Page(
            data=[Environment.from_dict(item) for item in data["data"]],
            has_more=data["has_more"],
            last_id=data.get("last_id"),
        )

    def iter(self, *, limit: int = 100, include_archived: bool = False) -> Iterator[Environment]:
        after_id = None
        while True:
            page = self.list(limit=limit, after_id=after_id, include_archived=include_archived)
            yield from page.data
            if not page.has_more or not page.last_id:
                return
            after_id = page.last_id

    def retrieve(self, environment_id: str) -> Environment:
        data = self._transport.request(
            "GET", f"/v1/environments/{_path_id(environment_id)}", retry=True
        )
        return Environment.from_dict(data)

    def update(
        self,
        environment_id: str,
        *,
        name: str | object = _UNSET,
        description: str | None | object = _UNSET,
        metadata: Mapping[str, str] | object = _UNSET,
        network: LimitedNetwork | UnrestrictedNetwork | Mapping[str, Any] | object = _UNSET,
    ) -> Environment:
        payload = _body(name=name, description=description, metadata=metadata, network=network)
        if not payload:
            raise ValueError("At least one environment field must be supplied")
        data = self._transport.request(
            "POST",
            f"/v1/environments/{_path_id(environment_id)}",
            json=payload,
        )
        return Environment.from_dict(data)

    def archive(self, environment_id: str) -> Environment:
        data = self._transport.request(
            "POST",
            f"/v1/environments/{_path_id(environment_id)}/archive",
            retry=True,
        )
        return Environment.from_dict(data)

    def delete(self, environment_id: str) -> None:
        self._transport.request(
            "DELETE",
            f"/v1/environments/{_path_id(environment_id)}",
            retry_connect_only=True,
        )


class Sessions:
    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def create(
        self,
        *,
        agent: str | AgentReference | Mapping[str, Any],
        environment_id: str,
        id: str | None = None,
        title: str | None | object = _UNSET,
        metadata: Mapping[str, str] | object = _UNSET,
    ) -> Session:
        payload = _body(
            id=id or str(uuid.uuid4()),
            agent=agent,
            environment_id=environment_id,
            title=title,
            metadata=metadata,
        )
        data = self._transport.request("POST", "/v1/sessions", json=payload, retry=True)
        return Session.from_dict(data)

    def list(
        self,
        *,
        limit: int = 20,
        after_id: str | None = None,
        include_archived: bool = False,
    ) -> Page[Session]:
        data = self._transport.request(
            "GET",
            "/v1/sessions",
            params=_params(limit=limit, after_id=after_id, include_archived=include_archived),
            retry=True,
        )
        return Page(
            data=[Session.from_dict(item) for item in data["data"]],
            has_more=data["has_more"],
            last_id=data.get("last_id"),
        )

    def iter(self, *, limit: int = 100, include_archived: bool = False) -> Iterator[Session]:
        after_id = None
        while True:
            page = self.list(limit=limit, after_id=after_id, include_archived=include_archived)
            yield from page.data
            if not page.has_more or not page.last_id:
                return
            after_id = page.last_id

    def retrieve(self, session_id: str) -> Session:
        data = self._transport.request("GET", f"/v1/sessions/{_path_id(session_id)}", retry=True)
        return Session.from_dict(data)

    def archive(self, session_id: str) -> Session:
        data = self._transport.request(
            "POST", f"/v1/sessions/{_path_id(session_id)}/archive", retry=True
        )
        return Session.from_dict(data)

    def send_message(self, session_id: str, *, content: str) -> SendMessageResponse:
        data = self._transport.request(
            "POST",
            f"/v1/sessions/{_path_id(session_id)}/messages",
            json={"content": content},
        )
        return SendMessageResponse.from_dict(data)

    def list_events(self, session_id: str, *, after_seq: int = 0, limit: int = 100) -> EventPage:
        data = self._transport.request(
            "GET",
            f"/v1/sessions/{_path_id(session_id)}/events",
            params=_params(after_seq=after_seq, limit=limit),
            retry=True,
        )
        return EventPage(
            data=[session_event_from_dict(item) for item in data["data"]],
            has_more=data["has_more"],
            last_seq=data["last_seq"],
        )

    def iter_events(
        self, session_id: str, *, after_seq: int = 0, limit: int = 500
    ) -> Iterator[SessionEvent]:
        cursor = after_seq
        while True:
            page = self.list_events(session_id, after_seq=cursor, limit=limit)
            yield from page.data
            if not page.has_more or not page.data:
                return
            cursor = page.data[-1].seq

    def stream_events(self, session_id: str, *, after_seq: int = 0) -> EventStream:
        return EventStream(self._transport, session_id, after_seq=after_seq)

    def wait_until_ready(
        self, session_id: str, *, timeout: float = 180, poll_interval: float = 1
    ) -> Session:
        deadline = time.monotonic() + timeout
        while True:
            session = self.retrieve(session_id)
            if session.status == "ready":
                return session
            if session.status in {"failed", "archived"}:
                raise FunkyError(f"Session {session_id} entered terminal status {session.status!r}")
            if time.monotonic() >= deadline:
                raise APITimeoutError(f"Timed out waiting for session {session_id} to be ready")
            time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))

    def wait_for_turn(
        self,
        session_id: str,
        *,
        after_seq: int = 0,
        timeout: float = 300,
        poll_interval: float = 1,
    ) -> SessionEvent:
        deadline = time.monotonic() + timeout
        cursor = after_seq
        while True:
            page = self.list_events(session_id, after_seq=cursor, limit=500)
            for event in page.data:
                cursor = event.seq
                if event.type in {"turn_completed", "turn_failed"}:
                    return event
            if page.has_more and page.data:
                continue
            if time.monotonic() >= deadline:
                raise APITimeoutError(f"Timed out waiting for a turn in session {session_id}")
            time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))


class AsyncAgents:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def create(
        self,
        *,
        name: str,
        system_prompt: str,
        model: ModelConfig | Mapping[str, Any],
        id: str | None = None,
        description: str | None | object = _UNSET,
        metadata: Mapping[str, str] | object = _UNSET,
        tool_policy: Mapping[str, Any] | object = _UNSET,
        runtime: RuntimeConfig | Mapping[str, Any] | None | object = _UNSET,
    ) -> Agent:
        payload = _body(
            id=id or str(uuid.uuid4()),
            name=name,
            description=description,
            metadata=metadata,
            system_prompt=system_prompt,
            model=model,
            tool_policy=tool_policy,
            runtime=runtime,
        )
        return Agent.from_dict(
            await self._transport.request("POST", "/v1/agents", json=payload, retry=True)
        )

    async def list(
        self,
        *,
        limit: int = 20,
        after_id: str | None = None,
        include_archived: bool = False,
    ) -> Page[Agent]:
        data = await self._transport.request(
            "GET",
            "/v1/agents",
            params=_params(limit=limit, after_id=after_id, include_archived=include_archived),
            retry=True,
        )
        return Page(
            [Agent.from_dict(item) for item in data["data"]],
            data["has_more"],
            data.get("last_id"),
        )

    async def iter(
        self, *, limit: int = 100, include_archived: bool = False
    ) -> AsyncIterator[Agent]:
        after_id = None
        while True:
            page = await self.list(
                limit=limit, after_id=after_id, include_archived=include_archived
            )
            for item in page.data:
                yield item
            if not page.has_more or not page.last_id:
                return
            after_id = page.last_id

    async def retrieve(self, agent_id: str) -> Agent:
        return Agent.from_dict(
            await self._transport.request("GET", f"/v1/agents/{_path_id(agent_id)}", retry=True)
        )

    async def update(
        self,
        agent_id: str,
        *,
        name: str | object = _UNSET,
        description: str | None | object = _UNSET,
        metadata: Mapping[str, str] | object = _UNSET,
        system_prompt: str | object = _UNSET,
        model: ModelConfig | Mapping[str, Any] | object = _UNSET,
        tool_policy: Mapping[str, Any] | object = _UNSET,
        runtime: RuntimeConfig | Mapping[str, Any] | None | object = _UNSET,
    ) -> Agent:
        payload = _body(
            name=name,
            description=description,
            metadata=metadata,
            system_prompt=system_prompt,
            model=model,
            tool_policy=tool_policy,
            runtime=runtime,
        )
        if not payload:
            raise ValueError("At least one agent field must be supplied")
        return Agent.from_dict(
            await self._transport.request("POST", f"/v1/agents/{_path_id(agent_id)}", json=payload)
        )

    async def archive(self, agent_id: str) -> Agent:
        return Agent.from_dict(
            await self._transport.request(
                "POST", f"/v1/agents/{_path_id(agent_id)}/archive", retry=True
            )
        )

    async def list_versions(
        self, agent_id: str, *, limit: int = 20, after_version: int | None = None
    ) -> VersionPage:
        data = await self._transport.request(
            "GET",
            f"/v1/agents/{_path_id(agent_id)}/versions",
            params=_params(limit=limit, after_version=after_version),
            retry=True,
        )
        return VersionPage(
            [AgentVersion.from_dict(item) for item in data["data"]], data["has_more"]
        )

    async def iter_versions(
        self, agent_id: str, *, limit: int = 100
    ) -> AsyncIterator[AgentVersion]:
        after_version = None
        while True:
            page = await self.list_versions(agent_id, limit=limit, after_version=after_version)
            for item in page.data:
                yield item
            if not page.has_more or not page.data:
                return
            after_version = page.data[-1].version

    async def retrieve_version(self, agent_id: str, version: int) -> AgentVersion:
        return AgentVersion.from_dict(
            await self._transport.request(
                "GET",
                f"/v1/agents/{_path_id(agent_id)}/versions/{version}",
                retry=True,
            )
        )


class AsyncEnvironments:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def create(
        self,
        *,
        name: str,
        id: str | None = None,
        description: str | None | object = _UNSET,
        metadata: Mapping[str, str] | object = _UNSET,
        network: LimitedNetwork | UnrestrictedNetwork | Mapping[str, Any] | object = _UNSET,
    ) -> Environment:
        payload = _body(
            id=id or str(uuid.uuid4()),
            name=name,
            description=description,
            metadata=metadata,
            network=network,
        )
        return Environment.from_dict(
            await self._transport.request("POST", "/v1/environments", json=payload, retry=True)
        )

    async def list(
        self,
        *,
        limit: int = 20,
        after_id: str | None = None,
        include_archived: bool = False,
    ) -> Page[Environment]:
        data = await self._transport.request(
            "GET",
            "/v1/environments",
            params=_params(limit=limit, after_id=after_id, include_archived=include_archived),
            retry=True,
        )
        return Page(
            [Environment.from_dict(item) for item in data["data"]],
            data["has_more"],
            data.get("last_id"),
        )

    async def iter(
        self, *, limit: int = 100, include_archived: bool = False
    ) -> AsyncIterator[Environment]:
        after_id = None
        while True:
            page = await self.list(
                limit=limit, after_id=after_id, include_archived=include_archived
            )
            for item in page.data:
                yield item
            if not page.has_more or not page.last_id:
                return
            after_id = page.last_id

    async def retrieve(self, environment_id: str) -> Environment:
        return Environment.from_dict(
            await self._transport.request(
                "GET", f"/v1/environments/{_path_id(environment_id)}", retry=True
            )
        )

    async def update(
        self,
        environment_id: str,
        *,
        name: str | object = _UNSET,
        description: str | None | object = _UNSET,
        metadata: Mapping[str, str] | object = _UNSET,
        network: LimitedNetwork | UnrestrictedNetwork | Mapping[str, Any] | object = _UNSET,
    ) -> Environment:
        payload = _body(name=name, description=description, metadata=metadata, network=network)
        if not payload:
            raise ValueError("At least one environment field must be supplied")
        return Environment.from_dict(
            await self._transport.request(
                "POST",
                f"/v1/environments/{_path_id(environment_id)}",
                json=payload,
            )
        )

    async def archive(self, environment_id: str) -> Environment:
        return Environment.from_dict(
            await self._transport.request(
                "POST",
                f"/v1/environments/{_path_id(environment_id)}/archive",
                retry=True,
            )
        )

    async def delete(self, environment_id: str) -> None:
        await self._transport.request(
            "DELETE",
            f"/v1/environments/{_path_id(environment_id)}",
            retry_connect_only=True,
        )


class AsyncSessions:
    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def create(
        self,
        *,
        agent: str | AgentReference | Mapping[str, Any],
        environment_id: str,
        id: str | None = None,
        title: str | None | object = _UNSET,
        metadata: Mapping[str, str] | object = _UNSET,
    ) -> Session:
        payload = _body(
            id=id or str(uuid.uuid4()),
            agent=agent,
            environment_id=environment_id,
            title=title,
            metadata=metadata,
        )
        return Session.from_dict(
            await self._transport.request("POST", "/v1/sessions", json=payload, retry=True)
        )

    async def list(
        self,
        *,
        limit: int = 20,
        after_id: str | None = None,
        include_archived: bool = False,
    ) -> Page[Session]:
        data = await self._transport.request(
            "GET",
            "/v1/sessions",
            params=_params(limit=limit, after_id=after_id, include_archived=include_archived),
            retry=True,
        )
        return Page(
            [Session.from_dict(item) for item in data["data"]],
            data["has_more"],
            data.get("last_id"),
        )

    async def iter(
        self, *, limit: int = 100, include_archived: bool = False
    ) -> AsyncIterator[Session]:
        after_id = None
        while True:
            page = await self.list(
                limit=limit, after_id=after_id, include_archived=include_archived
            )
            for item in page.data:
                yield item
            if not page.has_more or not page.last_id:
                return
            after_id = page.last_id

    async def retrieve(self, session_id: str) -> Session:
        return Session.from_dict(
            await self._transport.request("GET", f"/v1/sessions/{_path_id(session_id)}", retry=True)
        )

    async def archive(self, session_id: str) -> Session:
        return Session.from_dict(
            await self._transport.request(
                "POST", f"/v1/sessions/{_path_id(session_id)}/archive", retry=True
            )
        )

    async def send_message(self, session_id: str, *, content: str) -> SendMessageResponse:
        data = await self._transport.request(
            "POST",
            f"/v1/sessions/{_path_id(session_id)}/messages",
            json={"content": content},
        )
        return SendMessageResponse.from_dict(data)

    async def list_events(
        self, session_id: str, *, after_seq: int = 0, limit: int = 100
    ) -> EventPage:
        data = await self._transport.request(
            "GET",
            f"/v1/sessions/{_path_id(session_id)}/events",
            params=_params(after_seq=after_seq, limit=limit),
            retry=True,
        )
        return EventPage(
            [session_event_from_dict(item) for item in data["data"]],
            data["has_more"],
            data["last_seq"],
        )

    async def iter_events(
        self, session_id: str, *, after_seq: int = 0, limit: int = 500
    ) -> AsyncIterator[SessionEvent]:
        cursor = after_seq
        while True:
            page = await self.list_events(session_id, after_seq=cursor, limit=limit)
            for event in page.data:
                yield event
            if not page.has_more or not page.data:
                return
            cursor = page.data[-1].seq

    def stream_events(self, session_id: str, *, after_seq: int = 0) -> AsyncEventStream:
        return AsyncEventStream(self._transport, session_id, after_seq=after_seq)

    async def wait_until_ready(
        self, session_id: str, *, timeout: float = 180, poll_interval: float = 1
    ) -> Session:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            session = await self.retrieve(session_id)
            if session.status == "ready":
                return session
            if session.status in {"failed", "archived"}:
                raise FunkyError(f"Session {session_id} entered terminal status {session.status!r}")
            if loop.time() >= deadline:
                raise APITimeoutError(f"Timed out waiting for session {session_id} to be ready")
            await asyncio.sleep(min(poll_interval, max(0, deadline - loop.time())))

    async def wait_for_turn(
        self,
        session_id: str,
        *,
        after_seq: int = 0,
        timeout: float = 300,
        poll_interval: float = 1,
    ) -> SessionEvent:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        cursor = after_seq
        while True:
            page = await self.list_events(session_id, after_seq=cursor, limit=500)
            for event in page.data:
                cursor = event.seq
                if event.type in {"turn_completed", "turn_failed"}:
                    return event
            if page.has_more and page.data:
                continue
            if loop.time() >= deadline:
                raise APITimeoutError(f"Timed out waiting for a turn in session {session_id}")
            await asyncio.sleep(min(poll_interval, max(0, deadline - loop.time())))
