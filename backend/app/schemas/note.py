import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    title: str | None = "无标题"
    content: str | None = ""
    content_json: dict | None = None
    subject: str | None = None
    route_id: uuid.UUID | None = None
    node_id: uuid.UUID | None = None
    parent_id: uuid.UUID | None = None


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    content_json: dict | None = None
    subject: str | None = None
    route_id: uuid.UUID | None = None
    node_id: uuid.UUID | None = None
    parent_id: uuid.UUID | None = None


class NoteTagSchema(BaseModel):
    id: uuid.UUID
    note_id: uuid.UUID
    tag_id: uuid.UUID
    content_text: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None
    context: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NoteSchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    content: str
    content_json: dict | None = None
    subject: str | None = None
    route_id: uuid.UUID | None = None
    node_id: uuid.UUID | None = None
    parent_id: uuid.UUID | None = None
    is_template: bool
    word_count: int
    created_at: datetime
    updated_at: datetime
    tags: list[NoteTagSchema] = []

    model_config = {"from_attributes": True}


class NoteTagCreate(BaseModel):
    tag_id: uuid.UUID
    content_text: str
    start_offset: int | None = None
    end_offset: int | None = None
    context: str | None = None


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    description: str | None = None


class TagSchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    name: str
    color: str | None = None
    is_system: bool
    description: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BatchDeleteRequest(BaseModel):
    ids: list[uuid.UUID] = Field(..., min_length=1, max_length=100, description="要删除的笔记ID列表，最多100条")


class BatchDeleteResponse(BaseModel):
    deleted_count: int = Field(description="实际删除的笔记数量")
    failed_ids: list[uuid.UUID] = Field(default_factory=list, description="删除失败的笔记ID（不存在或不属于当前用户）")
