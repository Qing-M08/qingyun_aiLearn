import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class LearningRouteCreate(BaseModel):
    topic: str = Field(max_length=255)
    goal: Optional[str] = None
    available_hours: Optional[float] = Field(None, gt=0)
    current_level: Optional[str] = Field(None, pattern="^(beginner|intermediate|advanced)$")
    preferences: Optional[dict] = None


class LearningRouteSchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    topic: str
    description: Optional[str] = None
    status: str
    total_steps: int
    current_step: int
    estimated_hours: Optional[float] = None
    metadata: Optional[dict] = Field(None, validation_alias="metadata_")
    created_at: datetime
    updated_at: datetime
    steps: list["LearningRouteStepSchema"] = []

    model_config = {"from_attributes": True, "populate_by_name": True}

    @classmethod
    def model_validate_orm(cls, obj):
        """从ORM对象创建schema，安全处理steps懒加载和metadata字段冲突。

        SQLAlchemy ORM 模型中 metadata 列映射为 Python 属性 metadata_（因 Base.metadata
        已被 SQLAlchemy MetaData 占用），此处显式排除 metadata 避免误取 MetaData 对象。
        """
        try:
            return cls.model_validate(obj, from_attributes=True)
        except Exception:
            # 回退：手动构建字段（跳过需要懒加载的 steps 和存在字段名冲突的 metadata）
            exclude_fields = {"steps", "metadata"}
            data = {k: getattr(obj, k) for k in cls.model_fields if k not in exclude_fields}
            data["metadata"] = getattr(obj, "metadata_", None)
            return cls(**data, steps=[])


class LearningRouteStepSchema(BaseModel):
    id: uuid.UUID
    route_id: uuid.UUID
    node_id: Optional[uuid.UUID] = None
    step_order: int
    title: str
    description: Optional[str] = None
    estimated_minutes: Optional[int] = None
    status: str
    prerequisites: list[uuid.UUID] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RouteStepComplete(BaseModel):
    duration_seconds: Optional[int] = None
    notes: Optional[str] = None


class LectureGenerateRequest(BaseModel):
    route_id: uuid.UUID
    step_id: uuid.UUID
    node_id: Optional[uuid.UUID] = None
    custom_instructions: Optional[str] = None


class LectureSchema(BaseModel):
    id: uuid.UUID
    route_id: Optional[uuid.UUID] = None
    step_id: Optional[uuid.UUID] = None
    user_id: uuid.UUID
    node_id: Optional[uuid.UUID] = None
    title: str
    content: str
    content_json: Optional[dict] = None
    source_urls: list[str] = []
    version: int
    status: str
    token_usage: int
    note_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LectureGenerateResponse(BaseModel):
    lecture_id: uuid.UUID
    status: str


class RouteGenerationLLMResponse(BaseModel):
    """LLM返回的学习路线JSON结构"""
    title: str
    description: str
    estimated_total_hours: float
    steps: list["RouteStepLLM"]


class RouteStepLLM(BaseModel):
    order: int
    node_id: Optional[str] = None
    title: str
    description: str
    estimated_minutes: int
    prerequisite_step_orders: list[int] = []


class BatchDeleteRoutesRequest(BaseModel):
    route_ids: list[uuid.UUID] = Field(..., min_length=1, description="要删除的路线 ID 列表，至少 1 条")


class FailedRouteItem(BaseModel):
    id: uuid.UUID
    reason: str


class BatchDeleteRoutesResponse(BaseModel):
    deleted_count: int
    failed_ids: list[FailedRouteItem] = []
