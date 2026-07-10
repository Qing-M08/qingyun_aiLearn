import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.review import (
    ReviewPlanSchema,
    ReviewCompleteRequest,
    ReviewContentRequest,
    ReviewContentResponse,
    ReviewStatsResponse,
    ReviewPlanListResponse,
)
from app.services.review_service import ReviewService

router = APIRouter(prefix="/review", tags=["复习系统"])


@router.get("/plans", response_model=ReviewPlanListResponse)
async def get_review_plans(
    status: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取复习计划列表"""
    items, total = await ReviewService.get_review_plans(
        db=db,
        user_id=current_user.id,
        status=status,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )
    return ReviewPlanListResponse(items=items, total=total)


@router.post("/plans/{plan_id}/complete")
async def complete_review(
    plan_id: uuid.UUID,
    data: ReviewCompleteRequest = ReviewCompleteRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    完成一次复习。
    使用SM-2算法重新计算下次复习时间。
    """
    return await ReviewService.complete_review(
        db=db,
        plan_id=plan_id,
        user_id=current_user.id,
        performance=data.performance,
        notes=data.notes,
    )


@router.post("/generate-content", response_model=ReviewContentResponse)
async def generate_review_content(
    data: ReviewContentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    为复习生成针对性内容。
    根据掌握度自动选择复习形式（闪卡/选择题/讲解），也可手动指定。
    """
    return await ReviewService.generate_review_content(
        db=db,
        node_id=data.node_id,
        user_id=current_user.id,
        review_type=data.review_type,
    )


@router.get("/stats", response_model=ReviewStatsResponse)
async def get_review_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取复习统计"""
    return await ReviewService.get_review_stats(db, current_user.id)
