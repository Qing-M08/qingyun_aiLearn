import uuid
from fastapi import APIRouter, Depends, Query
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.qa import (
    QASessionCreate,
    QASessionSchema,
    QAMessageCreate,
    QAMessageSchema,
    QAMessagePair,
    DiagnosticQuestionsResponse,
    QASessionListResponse,
)
from app.services.qa_service import QAService

router = APIRouter(prefix="/learning/qa", tags=["智能答疑"])


@router.post("/sessions", response_model=QASessionSchema, status_code=201)
async def create_session(
    data: QASessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建答疑会话"""
    return await QAService.create_session(
        db=db,
        user_id=current_user.id,
        lecture_id=data.lecture_id,
        node_id=data.node_id,
        topic=data.topic,
    )


@router.get("/sessions", response_model=QASessionListResponse)
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取答疑会话列表"""
    items, total = await QAService.list_sessions(db, current_user.id, page, page_size)
    return QASessionListResponse(items=items, total=total)


@router.post("/sessions/{session_id}/messages", response_model=QAMessagePair)
async def send_message(
    session_id: uuid.UUID,
    data: QAMessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    发送消息（非流式）。
    返回用户消息和AI回复。
    如需流式输出，请使用WebSocket /ws/qa-stream/{session_id}
    """
    user_msg, assistant_msg = await QAService.handle_message(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
        content=data.content,
    )
    return QAMessagePair(
        user_message=user_msg,
        assistant_message=assistant_msg,
    )


@router.get("/sessions/{session_id}/messages", response_model=list[QAMessageSchema])
async def get_messages(
    session_id: uuid.UUID,
    before: Optional[uuid.UUID] = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取会话历史消息"""
    return await QAService.get_messages(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
        before=before,
        limit=limit,
    )


@router.post("/diagnostic-questions", response_model=DiagnosticQuestionsResponse)
async def generate_diagnostic_questions(
    lecture_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """为讲义生成诊断性问题"""
    questions = await QAService.generate_diagnostic_questions(
        db=db, lecture_id=lecture_id, user_id=current_user.id,
    )
    return DiagnosticQuestionsResponse(questions=questions)
