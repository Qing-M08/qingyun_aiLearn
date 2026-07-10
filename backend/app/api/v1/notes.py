import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.note import BatchDeleteRequest, BatchDeleteResponse, NoteCreate, NoteSchema, NoteUpdate
from app.services.note_service import NoteService

router = APIRouter()


@router.get("", response_model=PaginatedResponse[NoteSchema])
async def list_notes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
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
    note = await NoteService.create_note(db, user.id, **body.model_dump(exclude_unset=True))
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
