import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class QASessionCreate(BaseModel):
    lecture_id: Optional[uuid.UUID] = None
    node_id: Optional[uuid.UUID] = None
    topic: Optional[str] = Field(None, max_length=255)


class QASessionSchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    lecture_id: Optional[uuid.UUID] = None
    node_id: Optional[uuid.UUID] = None
    topic: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QAMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class QAMessageSchema(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str  # "user" | "assistant"
    content: str
    metadata: Optional[dict] = Field(None, validation_alias="metadata_")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class QAMessagePair(BaseModel):
    """发送消息后的响应（用户消息 + AI回复）"""
    user_message: QAMessageSchema
    assistant_message: QAMessageSchema


class DiagnosticQuestion(BaseModel):
    type: str = Field(pattern="^(choice|short_answer)$")
    question: str
    options: Optional[list[str]] = None  # 仅选择题
    correct_answer: str
    explanation: str
    target_concept: str
    difficulty: int = Field(ge=1, le=5)


class DiagnosticQuestionsResponse(BaseModel):
    questions: list[DiagnosticQuestion]


class QASessionListResponse(BaseModel):
    items: list[QASessionSchema]
    total: int
