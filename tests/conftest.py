from __future__ import annotations

from typing import Any


def agent_json(**overrides: Any) -> dict[str, Any]:
    value = {
        "type": "agent",
        "id": "agent-1",
        "name": "Research agent",
        "description": None,
        "metadata": {},
        "version": 1,
        "system_prompt": "Be careful.",
        "model": {"provider": "anthropic", "model": "claude-sonnet-5"},
        "tool_policy": {},
        "runtime": {"type": "native"},
        "created_at": "2026-07-24T20:00:00.000Z",
        "updated_at": "2026-07-24T20:00:00.000Z",
        "archived_at": None,
    }
    value.update(overrides)
    return value


def environment_json(**overrides: Any) -> dict[str, Any]:
    value = {
        "type": "environment",
        "id": "environment-1",
        "name": "default",
        "description": None,
        "metadata": {},
        "network": {"type": "unrestricted"},
        "created_at": "2026-07-24T20:00:00.000Z",
        "updated_at": "2026-07-24T20:00:00.000Z",
        "archived_at": None,
    }
    value.update(overrides)
    return value


def session_json(**overrides: Any) -> dict[str, Any]:
    value = {
        "type": "session",
        "id": "session-1",
        "status": "ready",
        "agent": {"id": "agent-1", "version": 1},
        "environment_id": "environment-1",
        "title": None,
        "metadata": {},
        "created_at": "2026-07-24T20:00:00.000Z",
        "updated_at": "2026-07-24T20:00:00.000Z",
        "archived_at": None,
    }
    value.update(overrides)
    return value


def event_json(seq: int, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": event_type,
        "seq": seq,
        "session_id": "session-1",
        "created_at": "2026-07-24T20:00:03.000Z",
        "payload": payload,
    }
