from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.learning import LearningRoute, LearningRouteStep, Lecture
from app.models.note import Note
from app.models.tag import NoteTag, Tag

logger = structlog.get_logger()


class ContextBuilder:
    """
    根据 AgentSession 的 context_type 和 context_id，
    构建注入 system prompt 的上下文文本。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_context(self, context_type: str, context_id: str, user_id: str) -> str:
        if context_type == "note":
            return await self._build_note_context(context_id, user_id)
        elif context_type == "lecture":
            return await self._build_lecture_context(context_id)
        elif context_type == "route":
            return await self._build_route_context(context_id)
        return ""

    async def _build_note_context(self, note_id: str, user_id: str) -> str:
        """注入当前笔记的标题、内容摘要、标签、关联知识点"""
        result = await self.db.execute(
            select(Note).where(Note.id == note_id, Note.user_id == user_id)
        )
        note = result.scalar_one_or_none()
        if not note:
            return ""

        # 获取笔记标签
        tag_result = await self.db.execute(
            select(Tag.name).join(NoteTag).where(NoteTag.note_id == note.id)
        )
        tags = [row[0] for row in tag_result.fetchall()]

        # 截取笔记内容前 500 字作为上下文
        content_preview = (note.content or "")[:500]

        return (
            f"## 当前上下文：笔记\n"
            f"- 标题：{note.title}\n"
            f"- 学科：{note.subject or '未分类'}\n"
            f"- 标签：{', '.join(tags) if tags else '无'}\n"
            f"- 内容摘要：\n{content_preview}\n"
        )

    async def _build_lecture_context(self, lecture_id: str) -> str:
        """注入讲义的标题、关联知识点、内容摘要"""
        result = await self.db.execute(
            select(Lecture).where(Lecture.id == lecture_id)
        )
        lecture = result.scalar_one_or_none()
        if not lecture:
            return ""

        return (
            f"## 当前上下文：讲义\n"
            f"- 标题：{lecture.title}\n"
            f"- 内容摘要：\n{(lecture.content or '')[:500]}\n"
        )

    async def _build_route_context(self, route_id: str) -> str:
        """注入学习路线的主题、进度、步骤列表"""
        result = await self.db.execute(
            select(LearningRoute).where(LearningRoute.id == route_id)
        )
        route = result.scalar_one_or_none()
        if not route:
            return ""

        # 获取步骤列表
        steps_result = await self.db.execute(
            select(LearningRouteStep)
            .where(LearningRouteStep.route_id == route_id)
            .order_by(LearningRouteStep.step_order)
        )
        steps = steps_result.scalars().all()

        steps_text = "\n".join([
            f"  {s.step_order}. {s.title} ({'已完成' if s.status == 'completed' else '未完成'})"
            for s in steps
        ])

        return (
            f"## 当前上下文：学习路线\n"
            f"- 主题：{route.topic}\n"
            f"- 状态：{route.status}\n"
            f"- 步骤：\n{steps_text}\n"
        )
