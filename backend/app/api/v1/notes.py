import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.api.deps import get_current_user
from app.database import get_db
from app.models.note import Note
from app.models.user import User
from app.schemas.agent import OrganizeFromChatRequest, OrganizeFromChatResponse
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.note import (
    BatchDeleteRequest,
    BatchDeleteResponse,
    NoteCreate,
    NoteSchema,
    NoteUpdate,
    OrganizeNotesRequest,
    OrganizeNotesResponse,
)
from app.services.note_service import NoteService

logger = structlog.get_logger()

router = APIRouter()


@router.get("", response_model=PaginatedResponse[NoteSchema])
async def list_notes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    subject: str | None = None,
    search: str | None = None,
    sort_by: str = Query("updated_at", pattern="^(created_at|updated_at|word_count)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if search:
        notes, total = await NoteService.search_notes(db, user.id, search, page, page_size)
    else:
        notes, total = await NoteService.list_notes(db, user.id, page, page_size, subject, sort_by, sort_order)
    return PaginatedResponse(
        items=[NoteSchema.model_validate(n) for n in notes],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=NoteSchema, status_code=status.HTTP_201_CREATED)
async def create_note(
    body: NoteCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    create_data = body.model_dump(exclude_unset=True)
    notebook_id = create_data.pop("notebook_id", None)
    note = await NoteService.create_note(db, user.id, **create_data)

    # Sprint 11: 创建时可直接关联笔记本
    if notebook_id:
        from app.services.notebook_service import NotebookService
        try:
            await NotebookService.add_notes_to_notebook(db, notebook_id, user.id, [note.id])
            logger.info("note_added_to_notebook_on_create", note_id=str(note.id), notebook_id=str(notebook_id))
        except Exception as e:
            logger.warning("auto_add_to_notebook_failed", note_id=str(note.id), notebook_id=str(notebook_id), error=str(e))

    return NoteSchema.model_validate(note)


@router.post("/batch-delete", response_model=BatchDeleteResponse)
async def batch_delete_notes(
    body: BatchDeleteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted_count, failed_ids = await NoteService.batch_delete_notes(
        db, body.ids, user.id
    )
    return BatchDeleteResponse(deleted_count=deleted_count, failed_ids=failed_ids)


@router.post("/organize", response_model=OrganizeNotesResponse)
async def organize_notes(
    request: OrganizeNotesRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI 整理笔记

    将选中的多篇笔记提交给 AI 进行整理，生成一篇新的成果笔记。
    整理方式由 prompt 参数驱动（合并/摘要/对比/扩展等）。
    异步处理，通过 WebSocket 监听进度。
    """
    task_id = await NoteService.organize_notes(
        db=db,
        user_id=user.id,
        note_ids=request.note_ids,
        prompt=request.prompt,
    )
    return OrganizeNotesResponse(
        task_id=task_id,
        message=f"笔记整理任务已提交，共 {len(request.note_ids)} 篇笔记",
    )


@router.get("/{note_id}", response_model=NoteSchema)
async def get_note(
    note_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    note = await NoteService.get_note(db, note_id, user.id)
    return NoteSchema.model_validate(note)


@router.put("/{note_id}", response_model=NoteSchema)
async def update_note(
    note_id: uuid.UUID,
    body: NoteUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    note = await NoteService.update_note(db, note_id, user.id, **body.model_dump(exclude_unset=True))
    return NoteSchema.model_validate(note)


@router.delete("/{note_id}", response_model=MessageResponse)
async def delete_note(
    note_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await NoteService.delete_note(db, note_id, user.id)
    return MessageResponse(message="deleted")


# ---- Sprint 10: 整理到笔记 ----

@router.post("/{note_id}/organize-from-chat", status_code=202)
async def organize_from_chat(
    note_id: uuid.UUID,
    request: OrganizeFromChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """整理到笔记（从 AI 回复）

    用户点击 ChatPanel 中的"整理到笔记"按钮后调用。
    后端创建隐藏 Agent 会话，异步执行整理任务。
    通过 WebSocket /ws/organize-from-chat-progress/{task_id} 监听进度。
    """
    from app.services.agent.agent_service import AgentService
    from app.tasks.note_tasks import organize_from_chat_task

    # 1. 验证笔记归属当前用户
    try:
        note = await NoteService.get_note(db, note_id, user.id)
    except Exception:
        raise HTTPException(status_code=404, detail="笔记不存在或无权访问")

    # 2. 创建隐藏 Agent 会话
    agent_service = AgentService(db)
    hidden_session = await agent_service.create_hidden_session(
        user_id=str(user.id),
        context_type="note",
        context_id=str(note_id),
        title=f"笔记整理 - {note.title}",
    )

    # 3. 提交 Celery 异步任务
    task = organize_from_chat_task.delay(
        user_id_str=str(user.id),
        note_id_str=str(note_id),
        agent_session_id_str=str(hidden_session.id),
        ai_reply_content=request.ai_reply_content,
        selected_text=request.selected_text,
        user_prompt=request.user_prompt,
    )

    logger.info(
        "organize_from_chat_submitted",
        user_id=str(user.id),
        note_id=str(note_id),
        agent_session_id=str(hidden_session.id),
        task_id=task.id,
    )

    return OrganizeFromChatResponse(
        agent_session_id=str(hidden_session.id),
        task_id=task.id,
        message="整理任务已提交",
    )
