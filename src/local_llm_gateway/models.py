from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ModelInfo(BaseModel):
    id: str
    type: Literal["model"] = "model"
    display_name: str | None = None
    provider: str | None = None
    owned_by: str | None = None


class ModelListResponse(BaseModel):
    data: list[ModelInfo] = Field(default_factory=list)


class ProtocolName(StrEnum):
    anthropic = "anthropic"
    openai = "openai"


class StreamEventType(StrEnum):
    message_start = "message_start"
    message_delta = "message_delta"
    content_block_start = "content_block_start"
    content_block_delta = "content_block_delta"
    content_block_stop = "content_block_stop"
    message_stop = "message_stop"
    error = "error"


class SamplingParams(BaseModel):
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    stop_sequences: list[str] = Field(default_factory=list)


class CanonicalRequest(BaseModel):
    request_id: str
    protocol: ProtocolName
    api_key_id: str | None = None
    model: str
    messages: list[dict[str, Any]] = Field(default_factory=list)
    system: str | list[dict[str, Any]] | None = None
    max_tokens: int = 1024
    stream: bool = True
    sampling: SamplingParams = Field(default_factory=SamplingParams)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    tool_choice: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    stream_options: dict[str, Any] = Field(default_factory=dict)


class UsageInfo(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class CanonicalResponse(BaseModel):
    id: str
    type: Literal["message"] = "message"
    model: str
    role: Literal["assistant"] = "assistant"
    content: list[dict[str, Any]] = Field(default_factory=list)
    stop_reason: str | None = None
    stop_sequence: str | None = None
    created_at: str | None = None
    usage: UsageInfo = Field(default_factory=UsageInfo)


class CanonicalStreamEvent(BaseModel):
    event_type: StreamEventType
    index: int = 0
    delta: dict[str, Any] = Field(default_factory=dict)
    usage: UsageInfo | None = None
    stop_reason: str | None = None
    raw_provider_event: dict[str, Any] | None = None


class TokenCountRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    messages: list[dict[str, Any]] = Field(default_factory=list)
    system: str | list[dict[str, Any]] | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any | None = None
    metadata: dict[str, Any] | None = None


class TokenCountResponse(BaseModel):
    input_tokens: int


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    max_tokens: int = 1024
    messages: list[dict[str, Any]] = Field(default_factory=list)
    system: str | list[dict[str, Any]] | None = None
    stream: bool = True
    temperature: float | None = None
    top_p: float | None = None
    stop_sequences: list[str] | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any | None = None
    metadata: dict[str, Any] | None = None
    top_k: int | None = None
    stream_options: dict[str, Any] | None = None


class OpenAIChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str
    messages: list[dict[str, Any]] = Field(default_factory=list)
    max_tokens: int = 1024
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    stop: str | list[str] | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: Any | None = None
    metadata: dict[str, Any] | None = None
    stream_options: dict[str, Any] | None = None


@dataclass(frozen=True)
class ProviderTarget:
    provider: str
    model: str
    base_url: str
    display_name: str | None = None
    supports_messages: bool = True
    supports_stream: bool = True
    supports_count_tokens: bool = True
    supports_tools: bool = True
    supports_system: bool = True
    max_context_tokens: int = 8192


class Scope(StrEnum):
    messages_create = "messages:create"
    tokens_count = "tokens:count"
    models_list = "models:list"
    admin_read = "admin:read"
    admin_write = "admin:write"


class ApiKeyStatus(StrEnum):
    active = "active"
    revoked = "revoked"


class ApiKeyRecord(BaseModel):
    id: str
    name: str
    prefix: str
    key_hash: str
    scopes: list[str] = Field(default_factory=list)
    status: ApiKeyStatus = ApiKeyStatus.active
    created_at: str
    expires_at: str | None = None
    last_used_at: str | None = None
