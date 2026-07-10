import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.note import Note
from app.models.tag import NoteTag, Tag
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.note import NoteTagCreate, NoteTagSchema, TagCreate, TagSchema
from app.core.exceptions import NotFoundException

router = APIRouter()


@router.get("", response_model=list[TagSchema])
async def list_tags(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取系统标签 + 用户自定义标签"""
    result = await db.execute(
        select(Tag).where(
            (Tag.is_system == True) | (Tag.user_id == user.id)  # noqa: E712
        )
    )
    tags = result.scalars().all()
    return [TagSchema.model_validate(t) for t in tags]


@router.post("", response_model=TagSchema, status_code=status.HTTP_201_CREATED)
async def create_tag(
    body: TagCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tag = Tag(
        user_id=user.id,
        name=body.name,
        color=body.color,
        description=body.description,
    )
    db.add(tag)
    await db.flush()
    await db.refresh(tag)
    return TagSchema.model_validate(tag)


@router.post("/notes/{note_id}/tags", response_model=NoteTagSchema, status_code=status.HTTP_201_CREATED)
async def add_note_tag(
    note_id: uuid.UUID,
    body: NoteTagCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 验证笔记归属
    result = await db.execute(select(Note).where(Note.id == note_id, Note.user_id == user.id))
    if not result.scalar_one_or_none():
        raise NotFoundException("笔记不存在")

    note_tag = NoteTag(
        note_id=note_id,
        tag_id=body.tag_id,
        content_text=body.content_text,
        start_offset=body.start_offset,
        end_offset=body.end_offset,
        context=body.context,
    )
    db.add(note_tag)
    await db.flush()
    await db.refresh(note_tag)
    return NoteTagSchema.model_validate(note_tag)


@router.delete("/notes/{note_id}/tags/{tag_id}", response_model=MessageResponse)
async def remove_note_tag(
    note_id: uuid.UUID,
    tag_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(NoteTag).where(NoteTag.note_id == note_id, NoteTag.tag_id == tag_id)
    )
    note_tag = result.scalar_one_or_none()
    if not note_tag:
        raise NotFoundException("标签记录不存在")
    await db.delete(note_tag)
    await db.flush()
    return MessageResponse(message="removed")
