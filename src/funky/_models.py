from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar, cast

T = TypeVar("T")


def parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def to_wire(value: Any) -> Any:
    if is_dataclass(value):
        instance = cast(Any, value)
        return {key: to_wire(item) for key, item in asdict(instance).items() if item is not None}
    if isinstance(value, Mapping):
        return {key: to_wire(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_wire(item) for item in value]
    return value


@dataclass(slots=True)
class ModelConfig:
    provider: str
    model: str
    max_tokens: int | None = None
    temperature: float | None = None


@dataclass(slots=True)
class RuntimeConfig:
    type: str


@dataclass(slots=True)
class UnrestrictedNetwork:
    type: str = "unrestricted"


@dataclass(slots=True)
class LimitedNetwork:
    allowed_hosts: list[str] = field(default_factory=list)
    type: str = "limited"


@dataclass(slots=True)
class AgentReference:
    id: str
    version: int


def _model_config(value: Mapping[str, Any]) -> ModelConfig:
    return ModelConfig(
        provider=value["provider"],
        model=value["model"],
        max_tokens=value.get("max_tokens"),
        temperature=value.get("temperature"),
    )


def _runtime(value: Mapping[str, Any] | None) -> RuntimeConfig | None:
    return RuntimeConfig(type=value["type"]) if value is not None else None


@dataclass(slots=True)
class Agent:
    id: str
    name: str
    system_prompt: str
    model: ModelConfig
    version: int
    description: str | None
    metadata: dict[str, str]
    tool_policy: dict[str, Any]
    runtime: RuntimeConfig | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    type: str = "agent"

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Agent:
        return cls(
            id=value["id"],
            name=value["name"],
            description=value.get("description"),
            metadata=dict(value.get("metadata") or {}),
            version=value["version"],
            system_prompt=value["system_prompt"],
            model=_model_config(value["model"]),
            tool_policy=dict(value.get("tool_policy") or {}),
            runtime=_runtime(value.get("runtime")),
            created_at=parse_datetime(value["created_at"]),  # type: ignore[arg-type]
            updated_at=parse_datetime(value["updated_at"]),  # type: ignore[arg-type]
            archived_at=parse_datetime(value.get("archived_at")),
            type=value.get("type", "agent"),
        )


@dataclass(slots=True)
class AgentVersion:
    agent_id: str
    version: int
    system_prompt: str
    model: ModelConfig
    tool_policy: dict[str, Any]
    runtime: RuntimeConfig | None
    created_at: datetime
    created_by: str | None
    type: str = "agent_version"

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AgentVersion:
        return cls(
            agent_id=value["agent_id"],
            version=value["version"],
            system_prompt=value["system_prompt"],
            model=_model_config(value["model"]),
            tool_policy=dict(value.get("tool_policy") or {}),
            runtime=_runtime(value.get("runtime")),
            created_at=parse_datetime(value["created_at"]),  # type: ignore[arg-type]
            created_by=value.get("created_by"),
            type=value.get("type", "agent_version"),
        )


@dataclass(slots=True)
class Environment:
    id: str
    name: str
    description: str | None
    metadata: dict[str, str]
    network: UnrestrictedNetwork | LimitedNetwork
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    type: str = "environment"

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Environment:
        network_value = value["network"]
        network: UnrestrictedNetwork | LimitedNetwork
        if network_value.get("type") == "limited":
            network = LimitedNetwork(allowed_hosts=list(network_value.get("allowed_hosts") or []))
        else:
            network = UnrestrictedNetwork(type=network_value.get("type", "unrestricted"))
        return cls(
            id=value["id"],
            name=value["name"],
            description=value.get("description"),
            metadata=dict(value.get("metadata") or {}),
            network=network,
            created_at=parse_datetime(value["created_at"]),  # type: ignore[arg-type]
            updated_at=parse_datetime(value["updated_at"]),  # type: ignore[arg-type]
            archived_at=parse_datetime(value.get("archived_at")),
            type=value.get("type", "environment"),
        )


@dataclass(slots=True)
class Session:
    id: str
    status: str
    agent: AgentReference
    environment_id: str
    title: str | None
    metadata: dict[str, str]
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    type: str = "session"

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Session:
        agent = value["agent"]
        return cls(
            id=value["id"],
            status=value["status"],
            agent=AgentReference(id=agent["id"], version=agent["version"]),
            environment_id=value["environment_id"],
            title=value.get("title"),
            metadata=dict(value.get("metadata") or {}),
            created_at=parse_datetime(value["created_at"]),  # type: ignore[arg-type]
            updated_at=parse_datetime(value["updated_at"]),  # type: ignore[arg-type]
            archived_at=parse_datetime(value.get("archived_at")),
            type=value.get("type", "session"),
        )


@dataclass(slots=True)
class SendMessageResponse:
    turn: str
    seq: int

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> SendMessageResponse:
        return cls(turn=value["turn"], seq=value["seq"])


@dataclass(slots=True)
class Page(Generic[T]):
    data: list[T]
    has_more: bool
    last_id: str | None = None


@dataclass(slots=True)
class VersionPage:
    data: list[AgentVersion]
    has_more: bool


@dataclass(slots=True)
class EventPage:
    data: list[SessionEvent]
    has_more: bool
    last_seq: int


@dataclass(slots=True)
class TextContentBlock:
    text: str
    type: str = "text"


@dataclass(slots=True)
class UnknownContentBlock:
    type: str
    raw: dict[str, Any]


ContentBlock = TextContentBlock | UnknownContentBlock


def _content_block(value: Mapping[str, Any]) -> ContentBlock:
    if value.get("type") == "text":
        return TextContentBlock(text=value.get("text", ""), type="text")
    return UnknownContentBlock(type=str(value.get("type", "unknown")), raw=dict(value))


@dataclass(slots=True)
class ExecToolCall:
    cmd: str
    timeout_ms: int | None = None
    kind: str = "exec"


@dataclass(slots=True)
class UnknownToolCall:
    kind: str
    raw: dict[str, Any]


ToolCall = ExecToolCall | UnknownToolCall


def _tool_call(value: Mapping[str, Any]) -> ToolCall:
    if value.get("kind") == "exec":
        return ExecToolCall(cmd=value.get("cmd", ""), timeout_ms=value.get("timeout_ms"))
    return UnknownToolCall(kind=str(value.get("kind", "unknown")), raw=dict(value))


@dataclass(slots=True)
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass(slots=True)
class EmptyPayload:
    pass


@dataclass(slots=True)
class MessagePayload:
    content: list[ContentBlock]


@dataclass(slots=True)
class AssistantMessagePayload:
    content: list[ContentBlock]
    tool_calls: list[ToolCall]
    usage: Usage | None = None


@dataclass(slots=True)
class ToolResultPayload:
    idem_key: str
    output: str
    exit_code: int
    truncated: bool


@dataclass(slots=True)
class TurnFailedPayload:
    error_class: str
    message: str


@dataclass(slots=True)
class HarnessAttemptStartedPayload:
    attempt: str
    resumed_from: str | None


@dataclass(slots=True)
class SessionEvent:
    seq: int
    session_id: str
    created_at: datetime
    payload: Any
    type: str


@dataclass(slots=True)
class SessionProvisionedEvent(SessionEvent):
    payload: EmptyPayload
    type: str = "session_provisioned"


@dataclass(slots=True)
class UserMessageEvent(SessionEvent):
    payload: MessagePayload
    type: str = "user_message"


@dataclass(slots=True)
class AssistantMessageEvent(SessionEvent):
    payload: AssistantMessagePayload
    type: str = "assistant_message"


@dataclass(slots=True)
class ToolResultEvent(SessionEvent):
    payload: ToolResultPayload
    type: str = "tool_result"


@dataclass(slots=True)
class TurnCompletedEvent(SessionEvent):
    payload: EmptyPayload
    type: str = "turn_completed"


@dataclass(slots=True)
class TurnFailedEvent(SessionEvent):
    payload: TurnFailedPayload
    type: str = "turn_failed"


@dataclass(slots=True)
class HarnessAttemptStartedEvent(SessionEvent):
    payload: HarnessAttemptStartedPayload
    type: str = "harness_attempt_started"


@dataclass(slots=True)
class UnknownSessionEvent(SessionEvent):
    payload: dict[str, Any]
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RunTurnResult:
    output_text: str
    submission: SendMessageResponse
    events: list[SessionEvent]
    terminal_event: TurnCompletedEvent


def session_event_from_dict(value: Mapping[str, Any]) -> SessionEvent:
    event_type = str(value.get("type", "unknown"))
    raw_payload = value.get("payload")
    payload: dict[str, Any] = dict(raw_payload) if isinstance(raw_payload, Mapping) else {}
    common = {
        "seq": value["seq"],
        "session_id": value["session_id"],
        "created_at": parse_datetime(value["created_at"]),
    }
    if event_type == "session_provisioned":
        return SessionProvisionedEvent(payload=EmptyPayload(), **common)
    if event_type == "user_message":
        blocks = [_content_block(item) for item in payload.get("content", [])]
        return UserMessageEvent(payload=MessagePayload(blocks), **common)
    if event_type == "assistant_message":
        blocks = [_content_block(item) for item in payload.get("content", [])]
        calls = [_tool_call(item) for item in payload.get("tool_calls", [])]
        usage_value = payload.get("usage")
        usage = (
            Usage(
                input_tokens=usage_value["input_tokens"],
                output_tokens=usage_value["output_tokens"],
            )
            if isinstance(usage_value, dict)
            else None
        )
        return AssistantMessageEvent(
            payload=AssistantMessagePayload(blocks, calls, usage), **common
        )
    if event_type == "tool_result":
        return ToolResultEvent(
            payload=ToolResultPayload(
                idem_key=payload["idem_key"],
                output=payload["output"],
                exit_code=payload["exit_code"],
                truncated=payload["truncated"],
            ),
            **common,
        )
    if event_type == "turn_completed":
        return TurnCompletedEvent(payload=EmptyPayload(), **common)
    if event_type == "turn_failed":
        return TurnFailedEvent(
            payload=TurnFailedPayload(
                error_class=payload["error_class"], message=payload["message"]
            ),
            **common,
        )
    if event_type == "harness_attempt_started":
        return HarnessAttemptStartedEvent(
            payload=HarnessAttemptStartedPayload(
                attempt=payload["attempt"], resumed_from=payload.get("resumed_from")
            ),
            **common,
        )
    return UnknownSessionEvent(type=event_type, payload=dict(payload), raw=dict(value), **common)
