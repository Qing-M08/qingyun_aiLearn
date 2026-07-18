import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---- 请求 Schema ----

class NotebookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    summary: str | None = Field(None, max_length=1000)
    cover_color: str = Field("#F59E0B", pattern=r"^#[0-9A-Fa-f]{6}$")


class NotebookUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    summary: str | None = Field(None, max_length=1000)
    cover_color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")


class AddNotesRequest(BaseModel):
    note_ids: list[uuid.UUID] = Field(..., min_length=1, max_length=100)


class ReorderNotesRequest(BaseModel):
    order: list[uuid.UUID] = Field(..., min_length=1)


# ---- 响应 Schema ----

class TagBrief(BaseModel):
    id: uuid.UUID
    name: str
    color: str | None = None

    model_config = ConfigDict(from_attributes=True)


class NotePreview(BaseModel):
    id: uuid.UUID
    title: str
    word_count: int

    model_config = ConfigDict(from_attributes=True)


class NotebookBrief(BaseModel):
    """笔记本列表项 / 网格卡片"""
    id: uuid.UUID
    name: str
    summary: str | None
    cover_color: str
    note_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotebookDetail(NotebookBrief):
    """笔记本详情（含最近笔记预览）"""
    latest_notes: list[NotePreview] = []


class NotebookNoteItem(BaseModel):
    """目录中的笔记项"""
    note_id: uuid.UUID
    sort_order: int
    title: str
    word_count: int
    subject: str | None = None
    tags: list[TagBrief] = []
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AddNotesResponse(BaseModel):
    added: int
    skipped: int
    message: str


class ReorderResponse(BaseModel):
    message: str
    updated: int


class NotebookSearchResult(BaseModel):
    """笔记本内搜索结果"""
    note_id: uuid.UUID
    title: str
    highlight_title: str | None = None
    highlight_content: str | None = None
    word_count: int
    tags: list[TagBrief] = []
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotebookSearchResponse(BaseModel):
    items: list[NotebookSearchResult]
    total: int
    page: int
    page_size: int
    query: str
