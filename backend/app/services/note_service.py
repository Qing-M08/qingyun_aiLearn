import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundException
from app.core.utils import calculate_word_count
from app.models.note import Note
from app.models.tag import Tag, NoteTag
import structlog

logger = structlog.get_logger()


class NoteService:

    @staticmethod
    async def create_note(db: AsyncSession, user_id: uuid.UUID, **kwargs) -> Note:
        content = kwargs.get("content", "") or ""
        note = Note(
            user_id=user_id,
            title=kwargs.get("title", "无标题"),
            content=content,
            content_json=kwargs.get("content_json"),
            subject=kwargs.get("subject"),
            route_id=kwargs.get("route_id"),
            node_id=kwargs.get("node_id"),
            parent_id=kwargs.get("parent_id"),
            word_count=calculate_word_count(content),
        )
        db.add(note)
        await db.flush()
        # 重新查询并预加载 tags 关系，避免 Pydantic 序列化时触发懒加载
        result = await db.execute(
            select(Note)
            .options(selectinload(Note.tags))
            .where(Note.id == note.id)
        )
        return result.scalar_one()

    @staticmethod
    async def get_note(db: AsyncSession, note_id: uuid.UUID, user_id: uuid.UUID) -> Note:
        result = await db.execute(
            select(Note)
            .options(selectinload(Note.tags))
            .where(Note.id == note_id, Note.user_id == user_id)
        )
        note = result.scalar_one_or_none()
        if not note:
            raise NotFoundException("笔记不存在")
        return note

    @staticmethod
    async def list_notes(
        db: AsyncSession,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        subject: str | None = None,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> tuple[list[Note], int]:
        query = select(Note).where(Note.user_id == user_id)

        if subject:
            query = query.where(Note.subject == subject)

        # 排序
        sort_column = getattr(Note, sort_by, Note.updated_at)
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # 总数
        count_query = select(func.count()).select_from(Note).where(Note.user_id == user_id)
        if subject:
            count_query = count_query.where(Note.subject == subject)
        total_result = await db.execute(count_query)
        total = total_result.scalar()

        # 分页
        query = query.options(selectinload(Note.tags))
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        notes = list(result.scalars().all())

        return notes, total

    @staticmethod
    async def update_note(db: AsyncSession, note_id: uuid.UUID, user_id: uuid.UUID, **kwargs) -> Note:
        note = await NoteService.get_note(db, note_id, user_id)

        update_data = {k: v for k, v in kwargs.items() if v is not None}
        for field, value in update_data.items():
            setattr(note, field, value)

        # 重新计算字数
        if "content" in update_data:
            note.word_count = calculate_word_count(note.content or "")

        await db.flush()
        await db.refresh(note)
        return note

    @staticmethod
    async def get_or_create_tag(
        db: AsyncSession, name: str, user_id: uuid.UUID | None = None
    ) -> Tag:
        """获取或创建标签（按名称查找，不存在则创建）"""
        result = await db.execute(
            select(Tag).where(Tag.name == name)
        )
        tag = result.scalar_one_or_none()
        if not tag:
            tag = Tag(name=name, user_id=user_id)
            db.add(tag)
            await db.flush()
            await db.refresh(tag)
        return tag

    @staticmethod
    async def add_tag_to_note(
        db: AsyncSession, note_id: uuid.UUID, tag_id: uuid.UUID
    ) -> NoteTag:
        """为笔记添加标签"""
        note_tag = NoteTag(note_id=note_id, tag_id=tag_id)
        db.add(note_tag)
        await db.flush()
        return note_tag

    @staticmethod
    async def delete_note(db: AsyncSession, note_id: uuid.UUID, user_id: uuid.UUID):
        note = await NoteService.get_note(db, note_id, user_id)
        await db.delete(note)
        await db.flush()

    @staticmethod
    async def batch_delete_notes(
        db: AsyncSession, note_ids: list[uuid.UUID], user_id: uuid.UUID
    ) -> tuple[int, list[uuid.UUID]]:
        """批量删除笔记，返回 (实际删除数量, 失败ID列表)"""
        # 先查询属于当前用户的笔记
        result = await db.execute(
            select(Note).where(Note.id.in_(note_ids), Note.user_id == user_id)
        )
        found_notes = result.scalars().all()
        found_ids = {n.id for n in found_notes}

        # 计算失败的 ID（不存在或不属于当前用户）
        failed_ids = [nid for nid in note_ids if nid not in found_ids]

        # 逐条删除（cascade 自动清理关联标签）
        for note in found_notes:
            await db.delete(note)
        await db.flush()

        logger.info(
            "batch_delete_notes",
            requested=len(note_ids),
            deleted=len(found_notes),
            failed=len(failed_ids),
        )
        return len(found_notes), failed_ids

    @staticmethod
    async def search_notes(
        db: AsyncSession,
        user_id: uuid.UUID,
        query: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Note], int]:
        """基础数据库搜索（Sprint 2先用LIKE，后续替换为Meilisearch）"""
        search_filter = or_(
            Note.title.ilike(f"%{query}%"),
            Note.content.ilike(f"%{query}%"),
        )
        q = select(Note).where(Note.user_id == user_id, search_filter)

        count_q = select(func.count()).select_from(Note).where(Note.user_id == user_id, search_filter)
        total = (await db.execute(count_q)).scalar()

        q = q.options(selectinload(Note.tags))
        q = q.order_by(Note.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(q)
        return list(result.scalars().all()), total
