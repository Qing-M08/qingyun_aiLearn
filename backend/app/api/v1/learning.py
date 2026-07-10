import uuid
from fastapi import APIRouter, Depends, status
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.learning import (
    LearningRouteCreate,
    LearningRouteSchema,
    LearningRouteStepSchema,
    RouteStepComplete,
    LectureGenerateRequest,
    LectureSchema,
    LectureGenerateResponse,
    BatchDeleteRoutesRequest,
    BatchDeleteRoutesResponse,
)
from app.core.exceptions import NotFoundException
from app.services.learning_service import LearningService

router = APIRouter(prefix="/learning", tags=["学习引擎"])


@router.post("/routes", response_model=LearningRouteSchema, status_code=202)
async def create_route(
    data: LearningRouteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建学习路线。
    异步生成：返回status="generating"的路线，通过WebSocket推送完成状态。
    """
    route = await LearningService.create_route(
        db=db,
        user_id=current_user.id,
        topic=data.topic,
        goal=data.goal,
        available_hours=data.available_hours,
        current_level=data.current_level,
        preferences=data.preferences,
    )
    return LearningRouteSchema.model_validate_orm(route)


@router.get("/routes", response_model=list[LearningRouteSchema])
async def list_routes(
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用户学习路线列表"""
    return [LearningRouteSchema.model_validate_orm(r) for r in await LearningService.get_user_routes(db, current_user.id, status_filter)]


@router.delete("/routes/batch", response_model=BatchDeleteRoutesResponse)
async def batch_delete_routes(
    data: BatchDeleteRoutesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    批量删除学习路线。
    级联删除关联的 steps；lectures、QA sessions 等子资源的 route_id 置为 NULL。
    允许部分成功：某条不存在时不影响其他条删除。
    """
    result = await LearningService.batch_delete_routes(
        db=db, route_ids=data.route_ids, user_id=current_user.id
    )
    return BatchDeleteRoutesResponse(**result)


@router.delete("/routes/{route_id}", status_code=200)
async def delete_route(
    route_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    删除单条学习路线。
    级联删除关联的 steps；lectures、QA sessions 等子资源的 route_id 置为 NULL。
    路线不存在时返回 404。
    """
    deleted = await LearningService.delete_route(
        db=db, route_id=route_id, user_id=current_user.id
    )
    if not deleted:
        raise NotFoundException("学习路线不存在")
    return {"data": None}


@router.get("/routes/{route_id}", response_model=LearningRouteSchema)
async def get_route(
    route_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取学习路线详情（含步骤列表）"""
    return await LearningService.get_route(db, route_id, current_user.id)


@router.patch("/routes/{route_id}/steps/{step_id}/complete")
async def complete_step(
    route_id: uuid.UUID,
    step_id: uuid.UUID,
    data: RouteStepComplete = RouteStepComplete(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    标记步骤完成。
    副作用：触发AI动态调整后续路线（表现不佳加练习，表现优秀合并步骤）。
    """
    return await LearningService.complete_step(
        db=db,
        route_id=route_id,
        step_id=step_id,
        user_id=current_user.id,
        duration_seconds=data.duration_seconds,
        notes=data.notes,
    )


@router.post("/lectures/generate", response_model=LectureGenerateResponse, status_code=202)
async def generate_lecture(
    data: LectureGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    为某个学习步骤生成讲义。
    异步任务，通过WebSocket推送生成进度和结果。
    """
    lecture = await LearningService.create_lecture(
        db=db,
        user_id=current_user.id,
        route_id=data.route_id,
        step_id=data.step_id,
        node_id=data.node_id,
        custom_instructions=data.custom_instructions,
    )
    return LectureGenerateResponse(lecture_id=lecture.id, status="generating")


@router.get("/lectures/{lecture_id}", response_model=LectureSchema)
async def get_lecture(
    lecture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取讲义内容"""
    return await LearningService.get_lecture(db, lecture_id, current_user.id)
