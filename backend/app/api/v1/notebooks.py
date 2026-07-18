import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.database import get_db
from app.models.note import Note
from app.models.notebook import Notebook, NotebookNote
from app.models.user import User
from app.schemas.note import NoteSchema
from app.schemas.notebook import (
    AddNotesRequest,
    AddNotesResponse,
    NotebookBrief,
    NotebookCreate,
    NotebookDetail,
    NotebookNoteItem,
    NotebookSearchResponse,
    NotebookUpdate,
    NotePreview,
    ReorderNotesRequest,
    ReorderResponse,
)
from app.services.notebook_service import NotebookService

logger = structlog.get_logger()

router = APIRouter()


@router.post("", response_model=NotebookBrief, status_code=status.HTTP_201_CREATED)
async def create_notebook(
    body: NotebookCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建笔记本"""
    notebook = await NotebookService.create_notebook(
        db=db,
        user_id=user.id,
        name=body.name,
        summary=body.summary,
        cover_color=body.cover_color,
    )
    return NotebookBrief(
        id=notebook.id,
        name=notebook.name,
        summary=notebook.summary,
        cover_color=notebook.cover_color,
        note_count=0,
        created_at=notebook.created_at,
        updated_at=notebook.updated_at,
    )


@router.get("", response_model=dict)
async def list_notebooks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("updated_at", pattern="^(updated_at|created_at|name)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """笔记本列表"""
    items, total = await NotebookService.list_notebooks(
        db=db,
        user_id=user.id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{notebook_id}", response_model=NotebookDetail)
async def get_notebook(
    notebook_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """笔记本详情"""
    data = await NotebookService.get_notebook(db, notebook_id, user.id)
    return NotebookDetail(
        id=data["id"],
        name=data["name"],
        summary=data["summary"],
        cover_color=data["cover_color"],
        note_count=data["note_count"],
        latest_notes=[NotePreview(**n) for n in data["latest_notes"]],
        created_at=data["created_at"],
        updated_at=data["updated_at"],
    )


@router.put("/{notebook_id}", response_model=NotebookBrief)
async def update_notebook(
    notebook_id: uuid.UUID,
    body: NotebookUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新笔记本"""
    update_data = body.model_dump(exclude_unset=True)
    notebook = await NotebookService.update_notebook(db, notebook_id, user.id, update_data)
    # 查询 note_count
    from sqlalchemy import func, select
    from app.models.notebook import NotebookNote
    count_q = select(func.count(NotebookNote.id)).where(NotebookNote.notebook_id == notebook_id)
    note_count = (await db.execute(count_q)).scalar() or 0
    return NotebookBrief(
        id=notebook.id,
        name=notebook.name,
        summary=notebook.summary,
        cover_color=notebook.cover_color,
        note_count=note_count,
        created_at=notebook.created_at,
        updated_at=notebook.updated_at,
    )


@router.delete("/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notebook(
    notebook_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除笔记本（解散分组，笔记保留）"""
    await NotebookService.delete_notebook(db, notebook_id, user.id)
    return None


@router.get("/{notebook_id}/notes", response_model=dict)
async def get_notebook_notes(
    notebook_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取笔记本目录"""
    items, total = await NotebookService.get_notebook_notes(
        db=db,
        notebook_id=notebook_id,
        user_id=user.id,
        page=page,
        page_size=page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/{notebook_id}/notes", response_model=AddNotesResponse)
async def add_notes(
    notebook_id: uuid.UUID,
    body: AddNotesRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """添加笔记到笔记本"""
    return await NotebookService.add_notes_to_notebook(
        db=db,
        notebook_id=notebook_id,
        user_id=user.id,
        note_ids=body.note_ids,
    )


@router.delete("/{notebook_id}/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_note(
    notebook_id: uuid.UUID,
    note_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """从笔记本移除笔记"""
    await NotebookService.remove_note_from_notebook(db, notebook_id, user.id, note_id)
    return None


@router.put("/{notebook_id}/notes/reorder", response_model=ReorderResponse)
async def reorder_notes(
    notebook_id: uuid.UUID,
    body: ReorderNotesRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """批量更新笔记排序"""
    return await NotebookService.reorder_notebook_notes(
        db=db,
        notebook_id=notebook_id,
        user_id=user.id,
        ordered_ids=body.order,
    )


@router.get("/{notebook_id}/search", response_model=NotebookSearchResponse)
async def search_notebook(
    notebook_id: uuid.UUID,
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """笔记本内搜索"""
    return await NotebookService.search_in_notebook(
        db=db,
        notebook_id=notebook_id,
        user_id=user.id,
        query=q,
        page=page,
        page_size=page_size,
    )


@router.get("/{notebook_id}/available-notes", response_model=dict)
async def search_available_notes(
    notebook_id: uuid.UUID,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """搜索可添加到笔记本的笔记（排除已在笔记本中的笔记）"""
    # 验证笔记本归属
    notebook = await db.get(Notebook, notebook_id)
    if not notebook or notebook.user_id != user.id:
        raise HTTPException(status_code=404, detail="笔记本不存在")

    # 获取已在笔记本中的 note_ids
    existing_q = select(NotebookNote.note_id).where(NotebookNote.notebook_id == notebook_id)
    existing_result = await db.execute(existing_q)
    existing_ids = set(existing_result.scalars().all())

    # 查询用户笔记，排除已有的
    query = select(Note).where(Note.user_id == user.id, Note.id.notin_(existing_ids))

    # 搜索关键词
    if q:
        query = query.where(
            or_(
                Note.title.ilike(f"%{q}%"),
                Note.content.ilike(f"%{q}%"),
            )
        )

    # 总数
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # 分页
    query = query.options(selectinload(Note.tags))
    query = query.order_by(Note.updated_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    notes = result.scalars().all()

    items = [NoteSchema.model_validate(n).model_dump() for n in notes]
    return {"items": items, "total": total, "page": page, "page_size": page_size}
