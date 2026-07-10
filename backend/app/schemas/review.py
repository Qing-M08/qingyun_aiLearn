import uuid
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class ReviewPlanSchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    node_id: uuid.UUID
    review_type: str
    scheduled_at: datetime
    completed_at: Optional[datetime] = None
    status: str  # pending / completed / skipped
    priority: int
    metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
    # 关联信息
    node_name: Optional[str] = None
    node_subject: Optional[str] = None

    model_config = {"from_attributes": True}


class ReviewCompleteRequest(BaseModel):
    performance: Optional[float] = Field(None, ge=0.0, le=1.0, description="本次复习表现 0.0~1.0")
    notes: Optional[str] = None


class ReviewContentRequest(BaseModel):
    node_id: uuid.UUID
    review_type: Optional[str] = Field(None, pattern="^(flashcard|quiz|explanation)$")


class ReviewContentResponse(BaseModel):
    content: str
    type: str  # flashcard / quiz / explanation
    node_name: str


class ReviewStatsResponse(BaseModel):
    today_due: int
    this_week_completed: int
    overdue_count: int
    mastery_distribution: dict  # { not_started, learning, familiar, mastered }


class ReviewPlanListResponse(BaseModel):
    items: list[ReviewPlanSchema]
    total: int
