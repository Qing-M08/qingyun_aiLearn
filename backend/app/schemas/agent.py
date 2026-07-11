from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---- 请求 Schema ----

class CreateAgentSessionRequest(BaseModel):
    context_type: str = Field(default="general", pattern="^(general|note|lecture|route)$")
    context_id: str | None = None
    initial_message: str | None = None


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)


class ListSessionsRequest(BaseModel):
    status: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ListMessagesRequest(BaseModel):
    before: str | None = None
    limit: int = Field(default=50, ge=1, le=200)


class BatchDeleteSessionsRequest(BaseModel):
    session_ids: list[str] = Field(..., min_length=1, max_length=100)


class BatchDeleteSessionsResponse(BaseModel):
    deleted_count: int
    failed_ids: list[str] = []


# ---- 响应 Schema ----

class ToolCallResponse(BaseModel):
    id: str
    tool_name: str
    tool_display_name: str
    input: dict[str, Any]
    output: Any | None = None
    status: str
    error_message: str | None = None
    started_at: str
    completed_at: str | None = None


class AgentSessionResponse(BaseModel):
    id: str
    user_id: str
    title: str | None = None
    context_type: str
    context_id: str | None = None
    status: str
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj: Any) -> "AgentSessionResponse":
        if hasattr(obj, "id"):
            return cls(
                id=str(obj.id),
                user_id=str(obj.user_id),
                title=obj.title,
                context_type=obj.context_type,
                context_id=str(obj.context_id) if obj.context_id else None,
                status=obj.status,
                created_at=obj.created_at.isoformat() + "Z" if obj.created_at else "",
                updated_at=obj.updated_at.isoformat() + "Z" if obj.updated_at else "",
            )
        return super().model_validate(obj)


class AgentMessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    tool_calls: list[ToolCallResponse] = []
    metadata: dict[str, Any] = {}
    created_at: str

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj: Any) -> "AgentMessageResponse":
        if hasattr(obj, "id"):
            return cls(
                id=str(obj.id),
                session_id=str(obj.session_id),
                role=obj.role,
                content=obj.content,
                tool_calls=obj.tool_calls if isinstance(obj.tool_calls, list) else [],
                metadata=obj.metadata_ if hasattr(obj, "metadata_") else {},
                created_at=obj.created_at.isoformat() + "Z" if obj.created_at else "",
            )
        return super().model_validate(obj)


class SendMessageResponse(BaseModel):
    user_message: AgentMessageResponse
    assistant_message: AgentMessageResponse


class ToolDefinitionResponse(BaseModel):
    name: str
    display_name: str
    description: str
    icon: str


# ---- WebSocket 消息 Schema ----

class WSMessageThinking(BaseModel):
    type: str = "thinking"
    data: dict[str, str]


class WSMessageToolCallStart(BaseModel):
    type: str = "tool_call_start"
    data: dict[str, Any]


class WSMessageToolCallResult(BaseModel):
    type: str = "tool_call_result"
    data: dict[str, Any]


class WSMessageToken(BaseModel):
    type: str = "token"
    data: dict[str, str]


class WSMessageDone(BaseModel):
    type: str = "done"
    data: dict[str, Any]


class WSMessageError(BaseModel):
    type: str = "error"
    data: dict[str, str]


class WSMessageSessionCreated(BaseModel):
    type: str = "session_created"
    data: dict[str, Any]
