import uuid

from app.database import async_session_factory
from app.services.note_service import NoteService


async def _tool_search_notes(user_id: str, query: str, tag: str | None = None, limit: int = 5) -> str:
    """搜索笔记工具 handler"""
    async with async_session_factory() as db:
        service = NoteService()
        notes, _ = await service.search_notes(
            db, user_id=uuid.UUID(user_id), query=query, page=1, page_size=limit
        )
        if not notes:
            return "未找到相关笔记。"

        lines = []
        for n in notes:
            tags_list = [t.name for t in n.tags] if hasattr(n, "tags") and n.tags else []
            tags_str = ", ".join(tags_list) if tags_list else "无标签"
            preview = (n.content or "")[:150].replace("\n", " ")
            lines.append(f"📝 {n.title}\n  标签: {tags_str}\n  摘要: {preview}...")
        return "\n\n".join(lines)


async def _tool_get_note_content(user_id: str, note_id: str) -> str:
    """获取笔记内容工具 handler"""
    async with async_session_factory() as db:
        service = NoteService()
        try:
            note = await service.get_note(db, uuid.UUID(note_id), uuid.UUID(user_id))
            return f"标题：{note.title}\n学科：{note.subject or '未分类'}\n\n{note.content}"
        except Exception:
            return "笔记不存在或无权访问。"
