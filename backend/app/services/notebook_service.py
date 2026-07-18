import uuid
from datetime import datetime

import structlog
from fastapi import HTTPException
from sqlalchemy import bindparam, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.note import Note
from app.models.notebook import Notebook, NotebookNote
from app.models.tag import NoteTag, Tag
from app.schemas.notebook import (
    AddNotesResponse,
    NotebookBrief,
    NotebookDetail,
    NotebookNoteItem,
    NotebookSearchResponse,
    NotebookSearchResult,
    NotePreview,
    ReorderResponse,
    TagBrief,
)

logger = structlog.get_logger()


class NotebookService:

    @staticmethod
    async def create_notebook(
        db: AsyncSession, user_id: uuid.UUID, name: str, summary: str | None = None, cover_color: str = "#F59E0B"
    ) -> Notebook:
        notebook = Notebook(user_id=user_id, name=name, summary=summary, cover_color=cover_color)
        db.add(notebook)
        await db.flush()
        await db.refresh(notebook)
        logger.info("notebook_created", notebook_id=str(notebook.id), user_id=str(user_id))
        return notebook

    @staticmethod
    async def list_notebooks(
        db: AsyncSession,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> tuple[list[dict], int]:
        """返回笔记本列表（含 note_count），支持排序"""
        # 构建排序列
        sort_col = getattr(Notebook, sort_by, Notebook.updated_at)
        if sort_order == "asc":
            order_col = sort_col.asc()
        else:
            order_col = sort_col.desc()

        # 总数
        count_q = select(func.count(Notebook.id)).where(Notebook.user_id == user_id)
        total = (await db.execute(count_q)).scalar() or 0

        # 查询（LEFT JOIN 聚合 note_count）
        q = (
            select(
                Notebook,
                func.count(NotebookNote.id).label("note_count"),
            )
            .outerjoin(NotebookNote, Notebook.id == NotebookNote.notebook_id)
            .where(Notebook.user_id == user_id)
            .group_by(Notebook.id)
            .order_by(order_col)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(q)
        rows = result.all()

        items = []
        for notebook, note_count in rows:
            item = {
                "id": notebook.id,
                "name": notebook.name,
                "summary": notebook.summary,
                "cover_color": notebook.cover_color,
                "note_count": note_count or 0,
                "created_at": notebook.created_at,
                "updated_at": notebook.updated_at,
            }
            items.append(item)

        return items, total

    @staticmethod
    async def get_notebook(
        db: AsyncSession, notebook_id: uuid.UUID, user_id: uuid.UUID
    ) -> dict:
        """获取笔记本详情，含 note_count 和 latest_notes"""
        notebook = await db.get(Notebook, notebook_id)
        if not notebook or notebook.user_id != user_id:
            raise HTTPException(status_code=404, detail="笔记本不存在")

        # note_count
        count_q = select(func.count(NotebookNote.id)).where(NotebookNote.notebook_id == notebook_id)
        note_count = (await db.execute(count_q)).scalar() or 0

        # latest_notes: 最近修改的 3 篇笔记
        latest_q = (
            select(Note.id, Note.title, Note.word_count)
            .join(NotebookNote, Note.id == NotebookNote.note_id)
            .where(NotebookNote.notebook_id == notebook_id)
            .order_by(Note.updated_at.desc())
            .limit(3)
        )
        latest_result = await db.execute(latest_q)
        latest_notes = [
            {"id": row[0], "title": row[1], "word_count": row[2]}
            for row in latest_result.all()
        ]

        return {
            "id": notebook.id,
            "name": notebook.name,
            "summary": notebook.summary,
            "cover_color": notebook.cover_color,
            "note_count": note_count,
            "latest_notes": latest_notes,
            "created_at": notebook.created_at,
            "updated_at": notebook.updated_at,
        }

    @staticmethod
    async def update_notebook(
        db: AsyncSession,
        notebook_id: uuid.UUID,
        user_id: uuid.UUID,
        update_data: dict,
    ) -> Notebook:
        notebook = await db.get(Notebook, notebook_id)
        if not notebook or notebook.user_id != user_id:
            raise HTTPException(status_code=404, detail="笔记本不存在")

        if not update_data:
            raise HTTPException(status_code=422, detail="至少传入一个更新字段")

        for key, value in update_data.items():
            if value is not None:
                setattr(notebook, key, value)

        notebook.updated_at = datetime.utcnow()
        await db.flush()
        await db.refresh(notebook)
        logger.info("notebook_updated", notebook_id=str(notebook_id))
        return notebook

    @staticmethod
    async def delete_notebook(
        db: AsyncSession, notebook_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        notebook = await db.get(Notebook, notebook_id)
        if not notebook or notebook.user_id != user_id:
            raise HTTPException(status_code=404, detail="笔记本不存在")

        await db.delete(notebook)
        await db.flush()
        logger.info("notebook_deleted", notebook_id=str(notebook_id))

    @staticmethod
    async def get_notebook_notes(
        db: AsyncSession,
        notebook_id: uuid.UUID,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict], int]:
        """获取笔记本目录，按 sort_order 排序，含标签信息"""
        # 验证笔记本归属
        notebook = await db.get(Notebook, notebook_id)
        if not notebook or notebook.user_id != user_id:
            raise HTTPException(status_code=404, detail="笔记本不存在")

        # 总数
        count_q = select(func.count(NotebookNote.id)).where(NotebookNote.notebook_id == notebook_id)
        total = (await db.execute(count_q)).scalar() or 0

        # 查询目录（JOIN notes + note_tags + tags）
        q = (
            select(
                NotebookNote.note_id,
                NotebookNote.sort_order,
                Note.title,
                Note.word_count,
                Note.subject,
                Note.updated_at,
            )
            .join(Note, NotebookNote.note_id == Note.id)
            .where(NotebookNote.notebook_id == notebook_id)
            .order_by(NotebookNote.sort_order.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(q)
        rows = result.all()

        # 批量获取标签
        note_ids = [row[0] for row in rows]
        tags_map = await NotebookService._get_tags_for_notes(db, note_ids)

        items = []
        for row in rows:
            note_id = row[0]
            items.append({
                "note_id": note_id,
                "sort_order": row[1],
                "title": row[2],
                "word_count": row[3],
                "subject": row[4],
                "tags": tags_map.get(note_id, []),
                "updated_at": row[5],
            })

        return items, total

    @staticmethod
    async def _get_tags_for_notes(
        db: AsyncSession, note_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[dict]]:
        """批量获取笔记的标签信息"""
        if not note_ids:
            return {}

        q = (
            select(NoteTag.note_id, Tag.id, Tag.name, Tag.color)
            .join(Tag, NoteTag.tag_id == Tag.id)
            .where(NoteTag.note_id.in_(note_ids))
        )
        result = await db.execute(q)
        tags_map: dict[uuid.UUID, list[dict]] = {}
        for note_id, tag_id, tag_name, tag_color in result.all():
            if note_id not in tags_map:
                tags_map[note_id] = []
            tags_map[note_id].append({"id": tag_id, "name": tag_name, "color": tag_color})
        return tags_map

    @staticmethod
    async def add_notes_to_notebook(
        db: AsyncSession,
        notebook_id: uuid.UUID,
        user_id: uuid.UUID,
        note_ids: list[uuid.UUID],
    ) -> AddNotesResponse:
        # 验证笔记本归属
        notebook = await db.get(Notebook, notebook_id)
        if not notebook or notebook.user_id != user_id:
            raise HTTPException(status_code=404, detail="笔记本不存在")

        # 验证笔记归属当前用户
        notes_q = select(Note).where(Note.id.in_(note_ids), Note.user_id == user_id)
        notes_result = await db.execute(notes_q)
        valid_notes = notes_result.scalars().all()
        if len(valid_notes) != len(note_ids):
            raise HTTPException(status_code=403, detail="部分笔记不属于当前用户")

        # 查询已存在的笔记
        existing_q = select(NotebookNote.note_id).where(
            NotebookNote.notebook_id == notebook_id,
            NotebookNote.note_id.in_(note_ids),
        )
        existing_result = await db.execute(existing_q)
        existing_ids = set(existing_result.scalars().all())

        # 获取当前最大 sort_order
        max_order_q = select(func.max(NotebookNote.sort_order)).where(
            NotebookNote.notebook_id == notebook_id
        )
        max_order = (await db.execute(max_order_q)).scalar() or -1

        added = 0
        skipped = 0
        next_order = max_order + 1

        for note_id in note_ids:
            if note_id in existing_ids:
                skipped += 1
                continue
            entry = NotebookNote(
                notebook_id=notebook_id,
                note_id=note_id,
                sort_order=next_order,
            )
            db.add(entry)
            next_order += 1
            added += 1

        # 更新笔记本 updated_at
        notebook.updated_at = datetime.utcnow()
        await db.flush()

        message = f"已添加 {added} 篇笔记" if added else "无新增笔记"
        return AddNotesResponse(added=added, skipped=skipped, message=message)

    @staticmethod
    async def remove_note_from_notebook(
        db: AsyncSession,
        notebook_id: uuid.UUID,
        user_id: uuid.UUID,
        note_id: uuid.UUID,
    ) -> None:
        # 验证笔记本归属
        notebook = await db.get(Notebook, notebook_id)
        if not notebook or notebook.user_id != user_id:
            raise HTTPException(status_code=404, detail="笔记本不存在")

        entry_q = select(NotebookNote).where(
            NotebookNote.notebook_id == notebook_id,
            NotebookNote.note_id == note_id,
        )
        entry_result = await db.execute(entry_q)
        entry = entry_result.scalar_one_or_none()
        if not entry:
            raise HTTPException(status_code=404, detail="笔记不在该笔记本中")

        await db.delete(entry)
        await db.flush()

    @staticmethod
    async def reorder_notebook_notes(
        db: AsyncSession,
        notebook_id: uuid.UUID,
        user_id: uuid.UUID,
        ordered_ids: list[uuid.UUID],
    ) -> ReorderResponse:
        # 验证笔记本归属
        notebook = await db.get(Notebook, notebook_id)
        if not notebook or notebook.user_id != user_id:
            raise HTTPException(status_code=404, detail="笔记本不存在")

        # 查询当前笔记本内所有 note_ids
        current_q = select(NotebookNote.note_id).where(NotebookNote.notebook_id == notebook_id)
        current_result = await db.execute(current_q)
        current_ids = set(current_result.scalars().all())

        # 校验完整性
        ordered_set = set(ordered_ids)
        if len(ordered_ids) != len(current_ids) or ordered_set != current_ids:
            raise HTTPException(
                status_code=422,
                detail="排序数组必须包含笔记本内所有笔记且不能重复",
            )

        # 批量更新 sort_order
        update_values = [
            {"notebook_id": notebook_id, "note_id": nid, "sort_order": idx}
            for idx, nid in enumerate(ordered_ids)
        ]
        await db.execute(
            update(NotebookNote)
            .where(
                NotebookNote.notebook_id == notebook_id,
                NotebookNote.note_id == bindparam("note_id"),
            )
            .values(sort_order=bindparam("sort_order")),
            update_values,
        )
        await db.flush()

        return ReorderResponse(message="排序已更新", updated=len(ordered_ids))

    @staticmethod
    async def search_in_notebook(
        db: AsyncSession,
        notebook_id: uuid.UUID,
        user_id: uuid.UUID,
        query: str,
        page: int = 1,
        page_size: int = 20,
    ) -> NotebookSearchResponse:
        """笔记本内搜索：先查 note_ids，再用 Meilisearch filter 搜索"""
        from app.services.search_service import search_notes_by_ids, search_notes_by_ids_fallback

        # 验证笔记本归属
        notebook = await db.get(Notebook, notebook_id)
        if not notebook or notebook.user_id != user_id:
            raise HTTPException(status_code=404, detail="笔记本不存在")

        # 获取笔记本内所有 note_ids
        ids_q = select(NotebookNote.note_id).where(NotebookNote.notebook_id == notebook_id)
        ids_result = await db.execute(ids_q)
        note_ids = ids_result.scalars().all()

        if not note_ids:
            return NotebookSearchResponse(items=[], total=0, page=page, page_size=page_size, query=query)

        offset = (page - 1) * page_size

        # 尝试 Meilisearch，失败则降级
        try:
            ms_result = await search_notes_by_ids(
                query=query,
                note_ids=[str(nid) for nid in note_ids],
                offset=offset,
                limit=page_size,
            )
            hits = ms_result.get("hits", [])
            total = ms_result.get("estimatedTotalHits", ms_result.get("total", 0))

            # 获取标签
            hit_ids = [uuid.UUID(h["id"]) for h in hits if "id" in h]
            tags_map = await NotebookService._get_tags_for_notes(db, hit_ids)

            items = []
            for hit in hits:
                note_id = uuid.UUID(hit["id"])
                highlight = hit.get("_formatted", {})
                items.append(NotebookSearchResult(
                    note_id=note_id,
                    title=hit.get("title", ""),
                    highlight_title=highlight.get("title"),
                    highlight_content=highlight.get("content"),
                    word_count=hit.get("word_count", 0),
                    tags=[TagBrief(**t) for t in tags_map.get(note_id, [])],
                    updated_at=datetime.fromisoformat(hit["updated_at"]) if hit.get("updated_at") else datetime.utcnow(),
                ))

            return NotebookSearchResponse(items=items, total=total, page=page, page_size=page_size, query=query)

        except Exception as e:
            logger.warning("meilisearch_search_failed", error=str(e), fallback="ilike")
            # 降级为数据库 ILIKE 搜索
            fallback_notes = await search_notes_by_ids_fallback(
                db=db, query=query, note_ids=note_ids, offset=offset, limit=page_size
            )
            # 获取总数（降级查询）
            count_q = (
                select(func.count(Note.id))
                .where(Note.id.in_(note_ids))
                .where(
                    (Note.title.ilike(f"%{query}%")) | (Note.content.ilike(f"%{query}%"))
                )
            )
            total = (await db.execute(count_q)).scalar() or 0

            # 获取标签
            fallback_ids = [n.id for n in fallback_notes]
            tags_map = await NotebookService._get_tags_for_notes(db, fallback_ids)

            items = [
                NotebookSearchResult(
                    note_id=n.id,
                    title=n.title,
                    highlight_title=None,
                    highlight_content=None,
                    word_count=n.word_count,
                    tags=[TagBrief(**t) for t in tags_map.get(n.id, [])],
                    updated_at=n.updated_at,
                )
                for n in fallback_notes
            ]

            return NotebookSearchResponse(items=items, total=total, page=page, page_size=page_size, query=query)
