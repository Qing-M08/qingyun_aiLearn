import uuid

from pydantic import BaseModel


class MemoryEntry(BaseModel):
    """记忆条目 — 轻量Pydantic模型"""

    id: uuid.UUID
    memory_type: str  # knowledge / habit / preference
    topic: str
    summary: str  # 索引层摘要（≤100 token）
    relevance_score: float = 0.0
    full_data: dict | None = None


class HabitSummary(BaseModel):
    """个人习惯摘要（Push模式，嵌入system prompt）"""

    text: str  # 200-300 token的摘要文本
    weak_nodes: list[str] = []
    token_count: int = 0
